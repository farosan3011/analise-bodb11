"""Formatação de saída no terminal usando Rich."""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()


def _variacao(atual: Optional[int], anterior: Optional[int]) -> str:
    if atual is None or anterior is None:
        return "—"
    diff = anterior - atual  # positivo = avançou na fila
    if diff > 0:
        return f"[green]▲ +{diff}[/green]"
    elif diff < 0:
        return f"[red]▼ {diff}[/red]"
    return "[yellow]=[/yellow]"


def mostrar_resultado(dados: dict, anterior: Optional[dict] = None):
    """Exibe painel com dados do snapshot atual."""
    depre = dados.get("depre", "?")
    cidade = dados.get("cidade", "?")
    posicao = dados.get("posicao")
    valor = dados.get("valor") or "—"
    status = dados.get("status") or "—"
    capturado = dados.get("capturado_em", "agora")

    posicao_str = str(posicao) if posicao is not None else "—"
    if anterior:
        var = _variacao(posicao, anterior.get("posicao"))
        posicao_str += f"  ({var})"

    conteudo = (
        f"[bold]Capturado em:[/bold] {capturado}\n"
        f"[bold]Posição na fila:[/bold] {posicao_str}\n"
        f"[bold]Valor:[/bold] {valor}\n"
        f"[bold]Status:[/bold] {status}"
    )

    console.print(
        Panel(
            conteudo,
            title=f"[bold cyan]Precatório DEPRE #{depre} — {cidade}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # Exibe campos extras se disponíveis
    extras = {
        k: v
        for k, v in dados.items()
        if k not in {"depre", "cidade", "posicao", "valor", "status", "capturado_em"}
        and isinstance(v, str)
        and v
    }
    if extras:
        t = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        t.add_column("campo", style="dim")
        t.add_column("valor")
        for k, v in extras.items():
            t.add_row(k, v)
        console.print(t)


def mostrar_historico(snapshots: list[dict]):
    """Exibe tabela com histórico de posições."""
    if not snapshots:
        console.print("[yellow]Nenhum histórico encontrado.[/yellow]")
        return

    depre = snapshots[0].get("depre", "?")
    cidade = snapshots[0].get("cidade", "?")

    t = Table(
        title=f"Histórico DEPRE #{depre} — {cidade}",
        box=box.ROUNDED,
        show_lines=True,
    )
    t.add_column("Data / Hora", style="dim", min_width=19)
    t.add_column("Posição", justify="right", min_width=8)
    t.add_column("Variação", justify="center", min_width=9)
    t.add_column("Valor", min_width=16)
    t.add_column("Status", min_width=12)

    for i, snap in enumerate(snapshots):
        posicao = snap.get("posicao")
        anterior = snapshots[i + 1] if i + 1 < len(snapshots) else None
        pos_ant = anterior.get("posicao") if anterior else None

        posicao_str = str(posicao) if posicao is not None else "—"
        var_str = _variacao(posicao, pos_ant)

        t.add_row(
            snap.get("capturado_em", "—"),
            posicao_str,
            var_str,
            snap.get("valor") or "—",
            snap.get("status") or "—",
        )

    console.print(t)


def mostrar_lista(precatorios: list[dict]):
    """Exibe tabela com todos os precatórios rastreados."""
    if not precatorios:
        console.print("[yellow]Nenhum precatório rastreado ainda.[/yellow]")
        console.print(
            "Use [bold]python main.py buscar --cidade CIDADE --depre NUMERO[/bold] para começar."
        )
        return

    t = Table(title="Precatórios Rastreados", box=box.ROUNDED, show_lines=True)
    t.add_column("DEPRE", style="bold", min_width=10)
    t.add_column("Cidade", min_width=15)
    t.add_column("Última Posição", justify="right", min_width=14)
    t.add_column("Último Status", min_width=12)
    t.add_column("Última Captura", style="dim", min_width=19)
    t.add_column("Rastreado desde", style="dim", min_width=19)

    for p in precatorios:
        t.add_row(
            p.get("depre", "—"),
            p.get("cidade", "—"),
            str(p["ultima_posicao"]) if p.get("ultima_posicao") is not None else "—",
            p.get("ultimo_status") or "—",
            p.get("ultima_captura") or "—",
            p.get("criado_em") or "—",
        )

    console.print(t)


def mostrar_multiplos_resultados(resultados: list[dict]):
    """Exibe tabela quando a busca retorna múltiplos precatórios."""
    if not resultados:
        return

    t = Table(title="Resultados da Busca", box=box.ROUNDED, show_lines=True)

    # Coleta todos os campos únicos (exceto os internos)
    campos_internos = {"posicao", "valor", "status", "cidade", "depre"}
    todos_campos = []
    for r in resultados:
        for k in r.keys():
            if k not in campos_internos and k not in todos_campos:
                todos_campos.append(k)

    for c in todos_campos:
        t.add_column(c, min_width=10)

    for r in resultados:
        t.add_row(*[str(r.get(c, "")) for c in todos_campos])

    console.print(t)


def erro(msg: str):
    console.print(f"[bold red]Erro:[/bold red] {msg}")


def aviso(msg: str):
    console.print(f"[yellow]{msg}[/yellow]")


def sucesso(msg: str):
    console.print(f"[green]✓[/green] {msg}")
