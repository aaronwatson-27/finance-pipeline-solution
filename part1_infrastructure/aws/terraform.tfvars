# For finance domain use current bucket defaults
aws_profile   = "finance-platform-aws"
bucket_prefix = "aaron-fdp-"

domains = {
  finance = {}
}

role_trust = {
  data_engineer   = ["arn:aws:iam::586106643119:user/aaron-admin"]
  finance_analyst = ["arn:aws:iam::586106643119:user/aaron-admin"]
}
