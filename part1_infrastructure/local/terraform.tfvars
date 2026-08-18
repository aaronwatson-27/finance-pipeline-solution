# For finance domain use current bucket defaults
# Can override per domain though, e.g. sales = { landing_expiration_days = 7 }
domains = {
  finance = {}
}

# LocalStack's default account. Real AWS uses your IAM user ARN instead.
role_trust = {
  data_engineer   = ["arn:aws:iam::000000000000:root"]
  finance_analyst = ["arn:aws:iam::000000000000:root"]
}
