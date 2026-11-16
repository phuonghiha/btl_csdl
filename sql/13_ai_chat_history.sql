-- =============================================================================
-- 13_ai_chat_history.sql
-- Bo sung bang AI_CHAT_LICH_SU luu lich su hoi thoai chatbot theo tai khoan
-- (MaTK), giup giu nguyen hoi thoai sau khi dang xuat va dang nhap lai.
-- =============================================================================

USE quan_ly_khach_san;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS AI_CHAT_LICH_SU (
    MaChat BIGINT AUTO_INCREMENT PRIMARY KEY,
    MaTK BIGINT NOT NULL,
    VaiTro ENUM('user', 'assistant') NOT NULL,
    NoiDung MEDIUMTEXT NOT NULL,
    CheDo VARCHAR(40) NULL,
    DongCo VARCHAR(40) NULL,
    DuLieuKemJson JSON NULL,
    ThoiGianTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX IDX_AI_CHAT_TK_CHAT (MaTK, MaChat),
    CONSTRAINT FK_AI_CHAT_TK FOREIGN KEY (MaTK) REFERENCES TAI_KHOAN(MaTK) ON DELETE CASCADE
) ENGINE=InnoDB;
