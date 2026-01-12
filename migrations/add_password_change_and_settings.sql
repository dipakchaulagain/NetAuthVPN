-- Add password_must_change column to webui_users table
ALTER TABLE webui_users ADD COLUMN password_must_change BOOLEAN DEFAULT FALSE AFTER last_login;

-- Create site_settings table
CREATE TABLE IF NOT EXISTS site_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    site_title VARCHAR(128) DEFAULT 'VPN Manager',
    logo_path VARCHAR(255),
    favicon_path VARCHAR(255),
    theme_color VARCHAR(7) DEFAULT '#667eea',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by INT,
    FOREIGN KEY (updated_by) REFERENCES webui_users(id) ON DELETE SET NULL
);

-- Insert default settings
INSERT INTO site_settings (site_title, theme_color) VALUES ('VPN Manager', '#667eea');
