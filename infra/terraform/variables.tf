variable "hcloud_token" {
  description = "Hetzner Cloud API token. Never commit in plaintext."
  type        = string
  sensitive   = true
}

variable "server_name" {
  description = "Hetzner Cloud server name"
  type        = string
  default     = "discord-bots-prod"
}

variable "server_type" {
  description = "Hetzner server type (cx22 = 2 vCPU, 4 GB RAM)"
  type        = string
  default     = "cx22"
}

variable "location" {
  description = "Hetzner datacenter (nbg1, fsn1, hel1, ash, hil)"
  type        = string
  default     = "nbg1"

  validation {
    condition     = contains(["nbg1", "fsn1", "hel1", "ash", "hil"], var.location)
    error_message = "location must be one of: nbg1, fsn1, hel1, ash, hil."
  }
}

variable "ssh_key_name" {
  description = "Name of the SSH key to register on Hetzner"
  type        = string
}

variable "ssh_public_key_path" {
  description = "Path to the local SSH public key file"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "os_image" {
  description = "Hetzner OS image"
  type        = string
  default     = "debian-12"
}

variable "allowed_admin_ips" {
  description = "CIDR ranges allowed to reach SSH (ports 22 and 2222). Must not be empty in production."
  type        = list(string)

  validation {
    condition     = length(var.allowed_admin_ips) > 0
    error_message = "allowed_admin_ips must contain at least one CIDR. Refusing to open SSH to 0.0.0.0/0."
  }
}
