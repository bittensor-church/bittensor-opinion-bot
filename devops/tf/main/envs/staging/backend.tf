terraform {
  backend "s3" {
    bucket = "bittensor-opinion-bot-autsnt"
    key    = "staging/main.tfstate"
    region = "us-east-1"
  }
}
