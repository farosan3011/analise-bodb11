"""
Script de diagnóstico: carrega a página do TJSP em modo headless,
dumpa todos os campos do formulário, tira screenshot e exibe o HTML
da área de conteúdo principal.

Execução: python diagnostico_tjsp.py
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

TJSP_URL = "https://www.tjsp.jus.br/cac/scp/webRelPublicLstPagPrecatPendentes.aspx"
OUT_DIR = Path(__file__).parent


async def diagnosticar():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            ignore_https_errors=True,
        )
        page = await context.new_page()

        print(f"[*] Navegando para: {TJSP_URL}")
        try:
            resp = await page.goto(TJSP_URL, wait_until="domcontentloaded", timeout=30000)
            print(f"[*] Status HTTP: {resp.status}")
        except Exception as e:
            print(f"[!] Erro ao navegar: {e}")
            await browser.close()
            return

        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            print("[!] networkidle timeout — continuando mesmo assim")

        # Screenshot completo
        shot_path = OUT_DIR / "diagnostico_tjsp.png"
        await page.screenshot(path=str(shot_path), full_page=True)
        print(f"[*] Screenshot salvo em: {shot_path}")

        # URL final (após possíveis redirects)
        print(f"[*] URL final: {page.url}")

        # Título da página
        titulo = await page.title()
        print(f"[*] Título: {titulo}")

        # Todos os campos de formulário
        campos = await page.evaluate("""() => {
            const els = Array.from(document.querySelectorAll('input, select, textarea, button'));
            return els.map(el => ({
                tag: el.tagName,
                id: el.id || '',
                name: el.name || '',
                type: el.getAttribute('type') || '',
                value: (el.value || '').substring(0, 50),
                text: (el.innerText || el.textContent || '').trim().substring(0, 50),
                visible: el.offsetParent !== null
            }));
        }""")

        print(f"\n{'='*60}")
        print(f"CAMPOS DO FORMULÁRIO ({len(campos)} encontrados)")
        print('='*60)
        for c in campos:
            vis = "✓" if c["visible"] else "✗"
            print(f"  [{vis}] <{c['tag'].lower()}> "
                  f"id='{c['id']}' name='{c['name']}' "
                  f"type='{c['type']}' text='{c['text']}' value='{c['value']}'")

        # Salva campos em JSON para referência
        campos_path = OUT_DIR / "diagnostico_campos.json"
        campos_path.write_text(json.dumps(campos, ensure_ascii=False, indent=2))
        print(f"\n[*] Campos salvos em: {campos_path}")

        # Todos os <select> com suas opções
        selects = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('select')).map(sel => ({
                id: sel.id,
                name: sel.name,
                options: Array.from(sel.options).map(o => ({value: o.value, text: o.text.trim()}))
            }));
        }""")

        if selects:
            print(f"\n{'='*60}")
            print("DROPDOWNS E SUAS OPÇÕES")
            print('='*60)
            for s in selects:
                print(f"\n  <select> id='{s['id']}' name='{s['name']}' "
                      f"({len(s['options'])} opções)")
                for o in s["options"][:30]:
                    print(f"    value='{o['value']}' → '{o['text']}'")
                if len(s["options"]) > 30:
                    print(f"    ... +{len(s['options'])-30} opções omitidas")

        # Texto visível principal da página (primeiros 3000 chars)
        texto = await page.evaluate("""() => {
            const body = document.body;
            return body ? body.innerText.trim().substring(0, 3000) : '';
        }""")
        print(f"\n{'='*60}")
        print("TEXTO VISÍVEL DA PÁGINA (primeiros 3000 chars)")
        print('='*60)
        print(texto)

        # HTML do form principal
        form_html = await page.evaluate("""() => {
            const forms = document.querySelectorAll('form');
            return Array.from(forms).map((f, i) => ({
                index: i,
                id: f.id,
                action: f.action,
                method: f.method,
                html_snippet: f.outerHTML.substring(0, 2000)
            }));
        }""")

        if form_html:
            print(f"\n{'='*60}")
            print(f"FORMULÁRIOS ({len(form_html)} encontrados)")
            print('='*60)
            for f in form_html:
                print(f"\n  Form #{f['index']}: id='{f['id']}' action='{f['action']}' method='{f['method']}'")
                print(f"  HTML (primeiros 2000 chars):")
                print(f"  {f['html_snippet']}")

        await context.close()
        await browser.close()
        print(f"\n[✓] Diagnóstico concluído.")


if __name__ == "__main__":
    asyncio.run(diagnosticar())
