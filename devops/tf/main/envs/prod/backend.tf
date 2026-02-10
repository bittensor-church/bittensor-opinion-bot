terraform {
  backend "s3" {
    bucket = "bittensor-opinion-bot-autsnt"
    key    = "prod/main.tfstate"
    region = "us-east-1"
  }
}
