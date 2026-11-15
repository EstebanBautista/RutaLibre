mock_provider "aws" {}

# The root module with its default values: every module wired together
# produces a plan.
run "whole_stack_plans" {
  command = plan

  assert {
    condition     = output.evidence_bucket_name == "rutalibre-evidencias"
    error_message = "The evidence bucket keeps the name used on Backblaze."
  }

  assert {
    condition     = output.frontend_bucket_name == "rutalibre-frontend"
    error_message = "Unexpected frontend bucket name."
  }
}
