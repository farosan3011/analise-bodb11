"""
Scraper para o site de precatórios do TJSP.

O site é ASP.NET WebForms e bloqueia requisições HTTP diretas (403),
portanto usamos Playwright (browser real headless) para contornar isso.

Como os seletores exatos só podem ser confirmados na execução real,
usamos múltiplas estratégias de seleção com fallback e emitimos diagnóstico
quando algum campo não é encontrado.
"""

import asyncio
import re
from typing import Optional

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

TJSP_URL = "https://www.tjsp.jus.br/cac/scp/webRelPublicLstPagPrecatPendentes.aspx"

# Seletores candidatos para o campo DEPRE (tentados em ordem)
DEPRE_SELECTORS = [
    "input[id*='DEPRE']",
    "input[id*='Depre']",
    "input[id*='depre']",
    "input[id*='NumProc']",
    "input[id*='numProc']",
    "input[id*='Processo']",
    "input[name*='DEPRE']",
    "input[name*='depre']",
]

# Seletores candidatos para o dropdown de comarca/cidade
COMARCA_SELECTORS = [
    "select[id*='Comarca']",
    "select[id*='comarca']",
    "select[id*='Cidade']",
    "select[id*='cidade']",
    "select[id*='Municipio']",
    "select[name*='Comarca']",
    "select[name*='comarca']",
]

# Seletores para o botão de pesquisa
PESQUISA_SELECTORS = [
    "input[type='submit']",
    "button[type='submit']",
    "input[id*='Pesquis']",
    "input[id*='pesquis']",
    "input[id*='Buscar']",
    "input[id*='buscar']",
    "input[value*='Pesquisar']",
    "input[value*='Consultar']",
    "input[value*='Buscar']",
]


async def _find_element(page: Page, selectors: list[str]) -> Optional[str]:
    """Retorna o primeiro seletor que encontra um elemento visível na página."""
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                return sel
        except Exception:
            continue
    return None


async def _diagnostico_form(page: Page):
    """Imprime campos encontrados no formulário e salva screenshot para depuração."""
    campos = await page.evaluate("""() => {
        const inputs = Array.from(document.querySelectorAll('input, select, textarea'));
        return inputs.map(el => ({
            tag: el.tagName,
            id: el.id,
            name: el.name,
            type: el.type || '',
            value: el.value ? el.value.substring(0, 30) : ''
        })).filter(el => el.id || el.name);
    }""")
    print("\n[DIAGNÓSTICO] Campos encontrados no formulário:")
    for c in campos:
        print(f"  <{c['tag'].lower()}> id='{c['id']}' name='{c['name']}' type='{c['type']}'")
    print()

    screenshot_path = "debug_tjsp_error.png"
    await page.screenshot(path=screenshot_path, full_page=True)
    print(f"[DIAGNÓSTICO] Screenshot salvo em: {screenshot_path}")


async def _parse_table(page: Page) -> list[dict]:
    """
    Extrai todas as linhas da tabela de resultados.

    Prefere tabelas com cabeçalhos <th> e pelo menos 3 colunas, evitando
    as tables de layout que o ASP.NET gera para menus e estrutura da página.
    """
    try:
        await page.wait_for_selector("table", timeout=15000)
    except PlaywrightTimeout:
        return []

    linhas = await page.evaluate("""() => {
        const tables = Array.from(document.querySelectorAll('table'));

        // Prefere tabelas com <th> e múltiplas colunas (tabelas de dados)
        // Descarta tabelas com menos de 3 colunas ou sem headers
        let melhorTabela = null;
        let melhorScore = -1;

        for (const t of tables) {
            const headers = t.querySelectorAll('th');
            const rows = t.querySelectorAll('tr');
            const cols = rows[0] ? rows[0].querySelectorAll('th, td').length : 0;

            if (cols < 2) continue;

            // Score: prioriza tabelas com <th> e mais linhas de dados
            const score = (headers.length > 0 ? 100 : 0) + rows.length + cols;
            if (score > melhorScore) {
                melhorScore = score;
                melhorTabela = t;
            }
        }

        if (!melhorTabela) return [];

        const rows = Array.from(melhorTabela.querySelectorAll('tr'));
        const headerRow = rows[0];
        const headers = Array.from(headerRow.querySelectorAll('th, td')).map(
            el => el.innerText.trim()
        );

        const resultado = [];
        for (let i = 1; i < rows.length; i++) {
            const cells = Array.from(rows[i].querySelectorAll('td'));
            if (cells.length === 0) continue;
            const obj = {};
            cells.forEach((td, idx) => {
                const key = headers[idx] || `col${idx}`;
                obj[key] = td.innerText.trim();
            });
            resultado.push(obj);
        }
        return resultado;
    }""")

    return linhas


def _extrair_posicao(dados_linha: dict) -> Optional[int]:
    """Tenta extrair número de posição/ordem da linha."""
    chaves_posicao = ["posição", "posicao", "ordem", "Posição", "Ordem", "No.", "Nº", "seq"]
    for chave in chaves_posicao:
        for k, v in dados_linha.items():
            if chave.lower() in k.lower():
                nums = re.findall(r"\d+", str(v))
                if nums:
                    return int(nums[0])
    # Fallback conservador: primeira coluna cujo header sugere numeração
    for k, v in dados_linha.items():
        if any(p in k.lower() for p in ["num", "ord", "seq", "pos"]):
            nums = re.findall(r"^\d+$", str(v).strip())
            if nums:
                return int(nums[0])
    return None


def _extrair_valor(dados_linha: dict) -> Optional[str]:
    """Tenta extrair o valor monetário da linha."""
    chaves_valor = ["valor", "Valor", "montante", "Montante", "quantia"]
    for chave in chaves_valor:
        for k, v in dados_linha.items():
            if chave.lower() in k.lower() and v:
                return v
    return None


def _extrair_status(dados_linha: dict) -> Optional[str]:
    """Tenta extrair o status da linha."""
    chaves_status = ["status", "Status", "situação", "Situação", "situacao"]
    for chave in chaves_status:
        for k, v in dados_linha.items():
            if chave.lower() in k.lower() and v:
                return v
    return None


def _linha_contem_depre(linha: dict, depre: str) -> bool:
    """Verifica se alguma célula da linha contém o número DEPRE."""
    depre_normalizado = re.sub(r"\D", "", depre)
    for v in linha.values():
        celula = re.sub(r"\D", "", str(v))
        if depre_normalizado and depre_normalizado in celula:
            return True
    return False


async def buscar_precatorio(cidade: str, depre: str, headless: bool = True) -> Optional[dict]:
    """
    Busca o precatório no TJSP para a cidade e número DEPRE informados.

    Retorna um único dicionário com os dados encontrados (posicao, valor,
    status e todos os campos brutos da tabela), ou None se não encontrado.

    Quando a busca retorna múltiplas linhas (lista completa da fila), localiza
    a linha que contém o número DEPRE e usa sua posição na tabela.
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
        page = await context.new_page()

        try:
            print("[*] Acessando TJSP...")
            await page.goto(TJSP_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=20000)

            # -- Selecionar comarca/cidade --
            comarca_sel = await _find_element(page, COMARCA_SELECTORS)
            if comarca_sel:
                print(f"[*] Selecionando comarca: {cidade}")
                try:
                    await page.select_option(comarca_sel, label=cidade)
                except Exception:
                    options = await page.eval_on_selector_all(
                        f"{comarca_sel} option",
                        "els => els.map(o => ({value: o.value, text: o.innerText.trim()}))",
                    )
                    match = next(
                        (o for o in options if cidade.lower() in o["text"].lower()), None
                    )
                    if match:
                        await page.select_option(comarca_sel, value=match["value"])
                    else:
                        print(f"[!] Comarca '{cidade}' não encontrada. Opções disponíveis:")
                        for o in options[:20]:
                            print(f"    {o['text']}")
                        raise ValueError(f"Comarca '{cidade}' não encontrada na lista.")

                # Aguarda possível postback do ASP.NET UpdatePanel após trocar comarca
                await asyncio.sleep(1.5)
                await page.wait_for_load_state("networkidle", timeout=10000)
            else:
                print("[!] Campo de comarca não encontrado. Executando diagnóstico...")
                await _diagnostico_form(page)
                raise RuntimeError("Campo de comarca não localizado na página.")

            # -- Preencher número DEPRE --
            depre_sel = await _find_element(page, DEPRE_SELECTORS)
            if depre_sel:
                print(f"[*] Preenchendo DEPRE: {depre}")
                await page.fill(depre_sel, depre)
            else:
                print("[!] Campo DEPRE não encontrado. Executando diagnóstico...")
                await _diagnostico_form(page)
                raise RuntimeError("Campo DEPRE não localizado na página.")

            # -- Submeter formulário --
            pesquisa_sel = await _find_element(page, PESQUISA_SELECTORS)
            if pesquisa_sel:
                print("[*] Pesquisando...")
                await page.click(pesquisa_sel)
            else:
                await page.keyboard.press("Enter")

            await page.wait_for_load_state("networkidle", timeout=20000)

            # -- Parsear resultados --
            linhas = await _parse_table(page)

            if not linhas:
                texto_pagina = await page.inner_text("body")
                if any(
                    t in texto_pagina.lower()
                    for t in ["não encontrado", "nenhum", "sem resultado"]
                ):
                    print(f"[!] Nenhum resultado para DEPRE {depre} em {cidade}.")
                else:
                    print("[!] Tabela de resultados não encontrada. Diagnóstico:")
                    await _diagnostico_form(page)
                return None

            # -- Localizar a linha do precatório --
            # Se a busca filtrou corretamente, há 1 linha. Se retornou lista
            # completa da fila, procura a linha que contém o número DEPRE.
            linha_alvo = None
            posicao_na_fila = None

            if len(linhas) == 1:
                linha_alvo = linhas[0]
                posicao_na_fila = _extrair_posicao(linhas[0])
            else:
                print(f"[*] {len(linhas)} linhas retornadas — localizando DEPRE {depre}...")
                for i, linha in enumerate(linhas):
                    if _linha_contem_depre(linha, depre):
                        linha_alvo = linha
                        # Posição na fila = número da linha (1-based) se não houver coluna explícita
                        posicao_na_fila = _extrair_posicao(linha) or (i + 1)
                        print(f"[✓] DEPRE encontrado na linha {i + 1} de {len(linhas)}.")
                        break

                if linha_alvo is None:
                    print(f"[!] DEPRE {depre} não encontrado nas {len(linhas)} linhas retornadas.")
                    return None

            resultado = dict(linha_alvo)
            resultado["posicao"] = posicao_na_fila
            resultado["valor"] = _extrair_valor(linha_alvo) or linha_alvo.get("Valor", "")
            resultado["status"] = _extrair_status(linha_alvo) or linha_alvo.get("Status", "")
            resultado["cidade"] = cidade
            resultado["depre"] = depre
            resultado["total_fila"] = len(linhas) if len(linhas) > 1 else None

            print(f"[✓] Dados capturados — posição: {posicao_na_fila}")
            return resultado

        except Exception:
            # Salva screenshot para facilitar depuração em caso de erro inesperado
            try:
                await page.screenshot(path="debug_tjsp_erro.png", full_page=True)
                print("[!] Screenshot salvo em debug_tjsp_erro.png")
            except Exception:
                pass
            raise
        finally:
            await context.close()
            await browser.close()


def buscar(cidade: str, depre: str, headless: bool = True) -> Optional[dict]:
    """Interface síncrona para buscar_precatorio."""
    return asyncio.run(buscar_precatorio(cidade, depre, headless))
