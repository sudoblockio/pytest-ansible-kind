# DO NOT EDIT - Managed by tackle
resource "github_actions_repository_permissions" "this" {
  repository      = github_repository.this.name
  allowed_actions = "all"
  enabled         = true
}
