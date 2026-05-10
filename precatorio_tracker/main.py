#!/usr/bin/env python3
"""
Assistente de Rastreamento de Precatórios TJSP

Uso:
  python main.py buscar --cidade "São Paulo" --depre 12345
  python main.py historico --depre 12345
  python main.py historico --depre 12345 --cidade "São Paulo"
  python main.py listar
  python main.py atualizar
"""

import argparse

import database as db
import display
import scraper


def cmd_buscar(args):
    db.init_db()

    dados = scraper.buscar(args.cidade, args.depre, headless=not args.browser)

    if not dados:
        display.aviso(f"Nenhum dado encontrado para DEPRE {args.depre} em {args.cidade}.")
        return

    precatorio_id = db.upsert_precatorio(args.depre, args.cidade)
    salvo = db.save_snapshot(precatorio_id, dados)

    historico = db.get_history(args.depre, args.cidade)
    anterior = historico[1] if len(historico) > 1 else None

    dados_exibir = dados.copy()
    if historico:
        dados_exibir["capturado_em"] = historico[0]["capturado_em"]

    display.mostrar_resultado(dados_exibir, anterior=anterior)

    if not salvo:
        display.aviso("Posição e status inalterados desde a última consulta — nenhum novo snapshot gravado.")


def cmd_historico(args):
    db.init_db()
    cidade = getattr(args, "cidade", None)
    snapshots = db.get_history(args.depre, cidade)

    if not snapshots:
        display.aviso(f"Nenhum histórico para DEPRE {args.depre}.")
        return

    # Avisa se há registros em múltiplas cidades e cidade não foi filtrada
    if not cidade:
        cidades = {s["cidade"] for s in snapshots}
        if len(cidades) > 1:
            display.aviso(
                f"DEPRE {args.depre} rastreado em {len(cidades)} cidades: "
                + ", ".join(sorted(cidades))
                + ". Use --cidade para filtrar."
            )

    display.mostrar_historico(snapshots)


def cmd_listar(args):
    db.init_db()
    precatorios = db.list_all()
    display.mostrar_lista(precatorios)


def cmd_atualizar(args):
    db.init_db()
    rastreados = db.get_all_tracked()

    if not rastreados:
        display.aviso("Nenhum precatório rastreado. Use 'buscar' para adicionar.")
        return

    display.sucesso(f"Atualizando {len(rastreados)} precatório(s)...")

    erros = 0
    sem_mudanca = 0
    for item in rastreados:
        depre = item["depre"]
        cidade = item["cidade"]
        print(f"\n→ DEPRE {depre} — {cidade}")
        try:
            dados = scraper.buscar(cidade, depre, headless=not args.browser)
            if dados:
                precatorio_id = db.upsert_precatorio(depre, cidade)
                salvo = db.save_snapshot(precatorio_id, dados)
                historico = db.get_history(depre, cidade)
                anterior = historico[1] if len(historico) > 1 else None
                dados_exibir = dados.copy()
                if historico:
                    dados_exibir["capturado_em"] = historico[0]["capturado_em"]
                display.mostrar_resultado(dados_exibir, anterior=anterior)
                if not salvo:
                    display.aviso("Sem mudanças desde a última consulta.")
                    sem_mudanca += 1
            else:
                display.aviso(f"Sem dados para DEPRE {depre} em {cidade}.")
        except Exception as e:
            display.erro(f"Falha ao atualizar DEPRE {depre}: {e}")
            erros += 1

    print()
    partes = []
    if erros:
        partes.append(f"{erros} erro(s)")
    if sem_mudanca:
        partes.append(f"{sem_mudanca} sem mudança")
    if partes:
        display.aviso("Atualização concluída: " + ", ".join(partes) + ".")
    else:
        display.sucesso("Todos os precatórios atualizados com sucesso.")


def main():
    parser = argparse.ArgumentParser(
        description="Assistente de rastreamento de precatórios TJSP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python main.py buscar --cidade "São Paulo" --depre 12345
  python main.py historico --depre 12345
  python main.py historico --depre 12345 --cidade "São Paulo"
  python main.py listar
  python main.py atualizar
        """,
    )

    sub = parser.add_subparsers(dest="comando", required=True)

    # -- buscar --
    p_buscar = sub.add_parser("buscar", help="Busca e salva snapshot de um precatório")
    p_buscar.add_argument("--cidade", required=True, help="Nome da comarca/cidade")
    p_buscar.add_argument("--depre", required=True, help="Número do DEPRE")
    p_buscar.add_argument(
        "--browser",
        action="store_true",
        help="Abre o browser visível (útil para depuração)",
    )
    p_buscar.set_defaults(func=cmd_buscar)

    # -- historico --
    p_hist = sub.add_parser("historico", help="Exibe histórico de posições de um DEPRE")
    p_hist.add_argument("--depre", required=True, help="Número do DEPRE")
    p_hist.add_argument("--cidade", default=None, help="Filtrar por cidade (opcional)")
    p_hist.set_defaults(func=cmd_historico)

    # -- listar --
    p_list = sub.add_parser("listar", help="Lista todos os precatórios rastreados")
    p_list.set_defaults(func=cmd_listar)

    # -- atualizar --
    p_atualizar = sub.add_parser(
        "atualizar", help="Atualiza snapshots de todos os precatórios rastreados"
    )
    p_atualizar.add_argument(
        "--browser",
        action="store_true",
        help="Abre o browser visível (útil para depuração)",
    )
    p_atualizar.set_defaults(func=cmd_atualizar)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
