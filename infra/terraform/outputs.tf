output "server_ip" {
  description = "Public IPv4 address of the server"
  value       = hcloud_server.discord_bots.ipv4_address
}

output "server_ipv6" {
  description = "Public IPv6 address of the server"
  value       = hcloud_server.discord_bots.ipv6_address
}

output "server_id" {
  description = "Hetzner Cloud server ID"
  value       = hcloud_server.discord_bots.id
}

output "firewall_id" {
  description = "Hetzner Cloud firewall ID"
  value       = hcloud_firewall.discord_bots.id
}

output "ansible_inventory_snippet" {
  description = "Ready-to-use Ansible inventory entry"
  value       = <<-EOT
    [discord_bots]
    discord-bots-prod ansible_host=${hcloud_server.discord_bots.ipv4_address} ansible_user=bot-runner ansible_ssh_private_key_file=~/.ssh/id_ed25519

    [discord_bots:vars]
    ansible_python_interpreter=/usr/bin/python3
  EOT
}
