-- NetAuthVPN Database Schema
-- This creates the necessary tables for the web interface

USE radius;

-- Web UI Users Table (for authentication)
CREATE TABLE IF NOT EXISTS webui_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(128) NOT NULL,
    email VARCHAR(128) UNIQUE NOT NULL,
    role ENUM('Administrator', 'Operator', 'Viewer', 'Auditor') NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    password_must_change BOOLEAN DEFAULT FALSE,
    INDEX idx_username (username),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- VPN Users Table (manages VPN user accounts with LDAP sync)
CREATE TABLE IF NOT EXISTS vpn_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    full_name VARCHAR(128),
    email VARCHAR(128),
    ip_address VARCHAR(15) UNIQUE NOT NULL,
    ldap_synced BOOLEAN DEFAULT FALSE,
    last_sync TIMESTAMP NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_ip (ip_address)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- VPN User Routes Table (custom routes per user)
CREATE TABLE IF NOT EXISTS vpn_user_routes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vpn_user_id INT NOT NULL,
    route VARCHAR(32) NOT NULL,
    description VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vpn_user_id) REFERENCES vpn_users(id) ON DELETE CASCADE,
    INDEX idx_user (vpn_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Security Rules Table (per-user firewall rules)
CREATE TABLE IF NOT EXISTS security_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vpn_user_id INT NOT NULL,
    route VARCHAR(32) NOT NULL,
    protocol ENUM('tcp', 'udp', 'icmp', 'any') DEFAULT 'any',
    port VARCHAR(20),
    action ENUM('ACCEPT', 'DROP') DEFAULT 'ACCEPT',
    description VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (vpn_user_id) REFERENCES vpn_users(id) ON DELETE CASCADE,
    INDEX idx_user (vpn_user_id),
    INDEX idx_active (active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- DNS Records Table (custom DNS entries for /etc/hosts)
CREATE TABLE IF NOT EXISTS dns_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    ip_address VARCHAR(15) NOT NULL,
    description VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    enabled BOOLEAN DEFAULT TRUE,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES webui_users(id) ON DELETE SET NULL,
    UNIQUE KEY unique_hostname (hostname),
    INDEX idx_hostname (hostname)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Audit Log Table (tracks admin actions)
CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    action VARCHAR(128) NOT NULL,
    resource_type VARCHAR(64),
    resource_id INT,
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_created (created_at),
    INDEX idx_resource (resource_type, resource_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Site Settings Table (for customization)
CREATE TABLE IF NOT EXISTS site_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    site_title VARCHAR(128) DEFAULT 'NetAuthVPN',
    logo_path VARCHAR(255),
    favicon_path VARCHAR(255),
    theme_color VARCHAR(7) DEFAULT '#667eea',
    theme_color_secondary VARCHAR(7) DEFAULT '#764ba2',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by INT,
    FOREIGN KEY (updated_by) REFERENCES webui_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default site settings
INSERT INTO site_settings (site_title, theme_color, theme_color_secondary) 
VALUES ('NetAuthVPN', '#667eea', '#764ba2')
ON DUPLICATE KEY UPDATE id=id;
