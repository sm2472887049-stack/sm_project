/*
 Navicat Premium Data Transfer

 Source Server         : 111
 Source Server Type    : MySQL
 Source Server Version : 80034
 Source Host           : localhost:3306
 Source Schema         : cqzf

 Target Server Type    : MySQL
 Target Server Version : 80034
 File Encoding         : 65001

 Date: 25/05/2025 14:43:54
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `email` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `password_hash` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `created_at` datetime NULL DEFAULT NULL,
  `last_login` datetime NULL DEFAULT NULL,
  `is_active` tinyint(1) NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `username`(`username` ASC) USING BTREE,
  UNIQUE INDEX `email`(`email` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 4 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of users
-- ----------------------------
INSERT INTO `users` VALUES (1, 'admin', 'admin@example.com', 'pbkdf2:sha256:1000000$Rv29bL4vCieEO8Ba$8949a0a61bc1576587a6e26f52af4c1a31fd6ad92028ce02012fdbf1f6d200e1', '2025-02-27 14:20:31', '2025-02-27 14:21:05', 1);
INSERT INTO `users` VALUES (2, '111', 'sm2472877049@163.com', 'pbkdf2:sha256:1000000$U04ZTIJK90M9Eacb$2cca1a4c6846409fb99a605ed9d7fe0fa6c9e55cdad60adf41874f307b82a0d5', '2025-02-27 14:32:32', '2025-04-02 12:54:08', 1);
INSERT INTO `users` VALUES (3, 'qwe', '123@qq.com', 'pbkdf2:sha256:600000$t0Vdp3X7XpvUKtrj$842dbcb11e1cab77f7be9589e7211c262b860da0eb24d37c1ab61c4c118ee2eb', '2025-03-30 03:51:47', '2025-03-30 05:05:34', 1);
INSERT INTO `users` VALUES (4, '123', '123@11.com', 'pbkdf2:sha256:600000$rQDLoi1DABRWFS1b$f94d2228f3c2c3ef0699488d0486d0b47c895d658bade8ffc803f68becb384bb', '2025-03-30 09:45:43', '2025-03-30 09:45:50', 1);

SET FOREIGN_KEY_CHECKS = 1;
