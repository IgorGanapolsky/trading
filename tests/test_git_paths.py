from src.utils.git_paths import resolve_shared_repo_root


def test_resolve_shared_repo_root_for_primary_checkout(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    assert resolve_shared_repo_root(repo) == repo.resolve()


def test_resolve_shared_repo_root_for_git_worktree(tmp_path):
    repo = tmp_path / "repo"
    git_dir = repo / ".git"
    git_dir.mkdir(parents=True)

    worktree = repo / ".worktrees" / "feature"
    worktree.mkdir(parents=True)
    git_file = worktree / ".git"
    git_file.write_text(f"gitdir: {git_dir / 'worktrees' / 'feature'}\n", encoding="utf-8")

    nested_path = worktree / "src"
    nested_path.mkdir(parents=True)

    assert resolve_shared_repo_root(nested_path) == repo.resolve()
