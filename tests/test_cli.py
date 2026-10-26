from orchestrator.interfaces.cli import build_parser


def test_help_epilog():
    p = build_parser()
    assert "Command-line research pipeline only." in (p.epilog or "")


def test_defaults_and_b0_alias():
    p = build_parser()
    args = p.parse_args(["run", "matrix"])
    assert args.workers == 4
    assert args.n_runs == 3
    b0 = p.parse_args(["b0"])
    assert b0.kind == "b0"
    mw = p.parse_args(["make-workers"])
    assert mw.n == 4
