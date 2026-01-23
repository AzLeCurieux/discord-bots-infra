resource "hcloud_ssh_key" "main" {
  name       = var.ssh_key_name
  public_key = file(pathexpand(var.ssh_public_key_path))

  labels = {
    managed_by = "terraform"
    project    = "discord-bots"
  }
}

resource "hcloud_server" "discord_bots" {
  name        = var.server_name
  server_type = var.server_type
  image       = var.os_image
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.main.id]

  user_data = <<-EOF
    #cloud-config
    package_update: true
    package_upgrade: true
    packages:
      - curl
      - ca-certificates
      - gnupg

    ssh_pwauth: false

    users:
      - name: deploy
        groups: sudo
        sudo: "ALL=(ALL) NOPASSWD:/usr/bin/apt-get, /usr/bin/apt, /usr/bin/systemctl"
        shell: /bin/bash
        ssh_authorized_keys:
          - ${trimspace(file(pathexpand(var.ssh_public_key_path)))}

    runcmd:
      - systemctl disable --now bluetooth cups avahi-daemon 2>/dev/null || true
      - echo "cloud-init complete" > /root/.cloud-init-done
  EOF

  labels = {
    managed_by  = "terraform"
    project     = "discord-bots"
    environment = "production"
    os          = "debian-12"
  }

  lifecycle {
    prevent_destroy       = true
    ignore_changes        = [user_data]
  }
}

resource "hcloud_firewall" "discord_bots" {
  name = "${var.server_name}-firewall"

  # SSH is restricted to declared admin IPs.
  # Do not open to 0.0.0.0/0 in production.
  dynamic "rule" {
    for_each = var.allowed_admin_ips
    content {
      direction   = "in"
      protocol    = "tcp"
      port        = "22"
      source_ips  = [rule.value]
      description = "SSH initial bootstrap from ${rule.value}"
    }
  }

  dynamic "rule" {
    for_each = var.allowed_admin_ips
    content {
      direction   = "in"
      protocol    = "tcp"
      port        = "2222"
      source_ips  = [rule.value]
      description = "SSH hardened from ${rule.value}"
    }
  }

  # No inbound rules for monitoring ports.
  # Grafana and Prometheus are accessible via SSH tunnel only.

  labels = {
    managed_by = "terraform"
    project    = "discord-bots"
  }
}

resource "hcloud_firewall_attachment" "discord_bots" {
  firewall_id = hcloud_firewall.discord_bots.id
  server_ids  = [hcloud_server.discord_bots.id]
}
