-- y-coco データベース定義 (エンティティ定義書に準拠)
-- XAMPP の phpMyAdmin の「インポート」、または mysql コマンドで実行する。
CREATE DATABASE IF NOT EXISTS ycoco DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ycoco;

CREATE TABLE IF NOT EXISTS users (
  id         INT          NOT NULL AUTO_INCREMENT,
  username   VARCHAR(10)  NOT NULL,
  passhash   VARCHAR(256) NOT NULL,
  imagepath  VARCHAR(50)  NULL,
  admin_flg  INT          NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS event_post (
  id            INT           NOT NULL AUTO_INCREMENT,
  user_id       INT           NOT NULL,
  title         VARCHAR(50)   NOT NULL,
  description   VARCHAR(5000) NOT NULL,
  imagepath     VARCHAR(50)   NULL,
  `datetime`    DATE          NOT NULL,
  fee           INT           NULL DEFAULT 0,
  location      VARCHAR(100)  NULL,
  address       VARCHAR(100)  NOT NULL,
  parking_info  VARCHAR(100)  NULL,
  contact_info  VARCHAR(255)  NULL,
  created_at    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_event_datetime (`datetime`),
  CONSTRAINT fk_event_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS knowhow (
  id          INT          NOT NULL AUTO_INCREMENT,
  user_id     INT          NOT NULL,
  title       VARCHAR(50)  NOT NULL,
  detail      VARCHAR(500) NOT NULL,
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_knowhow_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- post_type: 1 = イベント / 2 = ノウハウ (post_id は対応する投稿の id。多態参照のため外部キーなし)
CREATE TABLE IF NOT EXISTS comment (
  id          INT          NOT NULL AUTO_INCREMENT,
  user_id     INT          NOT NULL,
  post_type   INT          NOT NULL,
  post_id     INT          NOT NULL,
  comment     VARCHAR(500) NOT NULL,
  created_at  TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_comment_post (post_type, post_id),
  CONSTRAINT fk_comment_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS notification (
  id           INT        NOT NULL AUTO_INCREMENT,
  senduser_id  INT        NOT NULL,
  receiver_id  INT        NOT NULL,
  post_type    INT        NOT NULL,
  post_id      INT        NOT NULL,
  created_at   TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  read_flg     INT        NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY ix_notification_receiver (receiver_id, read_flg),
  CONSTRAINT fk_notification_sender   FOREIGN KEY (senduser_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_notification_receiver FOREIGN KEY (receiver_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;