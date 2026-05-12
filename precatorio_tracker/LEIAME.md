# Rastreador de Precatórios TJSP

Ferramenta de linha de comando para buscar precatórios no site do TJSP,
salvar snapshots históricos e acompanhar a evolução da posição na fila de pagamento.

> **Importante:** o site do TJSP bloqueia acessos de servidores cloud.
> Execute esta ferramenta no seu computador pessoal ou da empresa (IP residencial/corporativo).

---

## Pré-requisitos

- Python 3.11 ou superior
- pip

---

## Instalação (primeira vez)

```bash
# 1. Entre na pasta da ferramenta
cd precatorio_tracker

# 2. Instale as dependências Python
pip install -r requirements.txt

# 3. Baixe o navegador Chromium (necessário para o Playwright)
playwright install chromium
```

---

## Uso

Pode executar de dentro da pasta `precatorio_tracker/` ou da raiz do repositório:

```bash
# Da raiz do repositório:
python precatorio_tracker/main.py buscar --cidade "São Paulo" --depre 12345

# Ou de dentro da pasta:
cd precatorio_tracker
python main.py buscar --cidade "São Paulo" --depre 12345
```

### Comandos disponíveis

#### `buscar` — Busca e salva snapshot
```bash
python main.py buscar --cidade "São Paulo" --depre 12345
```
- Abre o Chromium em segundo plano, preenche o formulário do TJSP e captura os dados.
- Salva o resultado no banco histórico (não duplica se não houver mudança).
- Exibe posição na fila, valor e status.

**Dica:** use `--browser` para abrir o Chrome visível e ver o que está acontecendo:
```bash
python main.py buscar --cidade "São Paulo" --depre 12345 --browser
```

#### `historico` — Ver linha do tempo de um precatório
```bash
python main.py historico --depre 12345
python main.py historico --depre 12345 --cidade "São Paulo"  # filtra por cidade
```

#### `listar` — Ver todos os precatórios rastreados
```bash
python main.py listar
```

#### `atualizar` — Atualizar todos de uma vez
```bash
python main.py atualizar
```
Faz uma nova busca para cada precatório já rastreado e salva novos snapshots quando houver mudança.

---

## Se o scraper não encontrar os campos do formulário

Na primeira execução, pode ser que os seletores CSS não correspondam aos IDs reais da página.
Nesse caso, o scraper imprime automaticamente um **diagnóstico** com todos os campos
encontrados e salva um screenshot `debug_tjsp_erro.png` na pasta atual.

1. Abra o screenshot para ver o que o browser carregou
2. Leia o diagnóstico no terminal — ele lista `id`, `name` e `type` de cada campo
3. Abra um issue ou informe os IDs encontrados para que os seletores sejam ajustados

---

## Banco de dados

O histórico fica salvo em `precatorio_tracker/data/precatorios.db` (SQLite).
O arquivo não é sincronizado com o git — é exclusivo da sua máquina.

---

## Estrutura dos arquivos

```
precatorio_tracker/
├── main.py         # CLI (ponto de entrada)
├── scraper.py      # Automação Playwright → TJSP
├── database.py     # Histórico SQLite
├── display.py      # Formatação no terminal (Rich)
├── requirements.txt
└── data/
    └── precatorios.db  # criado automaticamente
```
