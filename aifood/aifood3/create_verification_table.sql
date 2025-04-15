-- 选择数据库（根据您的实际数据库名调整）
USE aifood;

-- 创建验证码表
CREATE TABLE IF NOT EXISTS email_verification_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    code VARCHAR(10) NOT NULL,
    created_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    INDEX (email, code)
);

-- 为数据库表添加注释
ALTER TABLE email_verification_codes COMMENT = '存储邮箱验证码'; 