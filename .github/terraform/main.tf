# DO NOT EDIT - Managed by tackle
resource "github_repository" "this" {
  name                                    = "pytest-ansible-kind"
  description                             = "pytest plugin for testing ansible roles against k8s with kind"
  homepage_url                            = "https://sudoblock.io"
  visibility                              = "public"
  has_issues                              = true
  has_discussions                         = true
  has_projects                            = true
  has_wiki                                = true
  is_template                             = false
  allow_merge_commit                      = true
  allow_squash_merge                      = true
  allow_rebase_merge                      = true
  allow_auto_merge                        = false
  squash_merge_commit_title               = "PR_TITLE"
  squash_merge_commit_message             = "PR_BODY"
  merge_commit_title                      = "PR_TITLE"
  merge_commit_message                    = "PR_BODY"
  delete_branch_on_merge                  = true
  web_commit_signoff_required             = false
  has_downloads                           = false
  auto_init                               = false
  archived                                = false
  archive_on_destroy                      = false
  vulnerability_alerts                    = false
  ignore_vulnerability_alerts_during_read = false
  allow_update_branch                     = false
  topics                                  = []
}

resource "github_repository_collaborators" "this" {
  repository = github_repository.this.name
  user {
    username   = "sudoblockbot"
    permission = "admin"
  }
  team {
    team_id    = "internal"
    permission = "push"
  }
}

resource "github_issue_labels" "this" {
  repository = github_repository.this.name

  label {
    name        = "p1"
    color       = "F53636"
    description = "priority 1"
  }

  label {
    name        = "p2"
    color       = "EB7A34"
    description = "priority 2"
  }

  label {
    name        = "p3"
    color       = "EBC334"
    description = "priority 2"
  }

  label {
    name        = "security"
    color       = "FF0000"
    description = "security issue - p1"
  }

  label {
    name        = "wip"
    color       = "326fA8"
    description = "work in progress"
  }

  label {
    name        = "feature"
    color       = "32A852"
    description = "feature of some kind"
  }
}
