# DO NOT EDIT - Managed by tackle
resource "github_repository_ruleset" "prevent_non_bot_merge" {
  name        = "Prevent merging to default branch unless by admin (sudoblockbot)"
  repository  = github_repository.this.name
  target      = "branch"
  enforcement = "active"

  conditions {
    ref_name {
      include = ["~DEFAULT_BRANCH"]
      exclude = []
    }
  }

  rules {
    update                  = true
    required_linear_history = true
    non_fast_forward        = true
  }

  bypass_actors {
    actor_type  = "RepositoryRole"
    actor_id    = 5 # Admin
    bypass_mode = "always"
  }
}

resource "github_repository_ruleset" "conventional_commits" {
  name        = "Conventional Commits Policy"
  repository  = github_repository.this.name
  target      = "branch"
  enforcement = "active"

  conditions {
    ref_name {
      include = ["~DEFAULT_BRANCH"]
      exclude = []
    }
  }

  rules {
    commit_message_pattern {
      name     = "Conventional Commit Format"
      operator = "regex"
      pattern  = "^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\\([\\w\\-]+\\))?: .+"
      negate   = false
    }

    required_linear_history = true
    non_fast_forward        = true
  }
}
