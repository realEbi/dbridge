-- Dedicated disposable data and accounts. Application accounts deliberately have
-- no PROCESS, CONNECTION_ADMIN or SUPER privileges; only the observer can see
-- other accounts' threads. Never run this seed against a shared database.
CREATE DATABASE dbridge_test CHARACTER SET utf8mb4;
CREATE DATABASE dbridge_other CHARACTER SET utf8mb4;
CREATE USER 'dbridge'@'%' IDENTIFIED BY 'dbridge';
CREATE USER 'dbridge_second'@'%' IDENTIFIED BY 'dbridge_second';
CREATE USER 'dbridge_observer'@'%' IDENTIFIED BY 'dbridge_observer';
GRANT ALL ON dbridge_test.* TO 'dbridge'@'%', 'dbridge_second'@'%';
GRANT ALL ON dbridge_other.* TO 'dbridge'@'%', 'dbridge_second'@'%';
GRANT PROCESS ON *.* TO 'dbridge_observer'@'%';
GRANT SELECT ON performance_schema.* TO 'dbridge_observer'@'%';
GRANT SELECT ON dbridge_test.* TO 'dbridge_observer'@'%';
USE dbridge_test;
CREATE TABLE million_rows (n INT NOT NULL PRIMARY KEY, payload VARCHAR(32) NOT NULL);
CREATE TABLE digits (n INT NOT NULL);
INSERT INTO digits VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9);
INSERT INTO million_rows
SELECT 1+a.n+10*b.n+100*c.n+1000*d.n+10000*e.n+100000*f.n, REPEAT('x',32)
FROM digits a CROSS JOIN digits b CROSS JOIN digits c CROSS JOIN digits d
CROSS JOIN digits e CROSS JOIN digits f;
DROP TABLE digits;
CREATE TABLE persisted (marker VARCHAR(64) PRIMARY KEY);
CREATE TABLE procedure_effects (marker VARCHAR(64) PRIMARY KEY);
DELIMITER $$
CREATE PROCEDURE capped_insert(IN marker_value VARCHAR(64))
BEGIN
  SELECT n FROM million_rows ORDER BY n LIMIT 1000;
  INSERT INTO procedure_effects VALUES (marker_value);
END$$
DELIMITER ;
CREATE TABLE dbridge_other.parent (a INT NOT NULL, b INT NOT NULL, PRIMARY KEY (b,a));
CREATE TABLE child (
  id INT NOT NULL,
  a INT NOT NULL,
  b INT NOT NULL,
  label VARCHAR(40) NULL DEFAULT 'untitled' COMMENT 'display label',
  PRIMARY KEY (b,id),
  CONSTRAINT parent_pair FOREIGN KEY (b,a) REFERENCES dbridge_other.parent (b,a)
);
CREATE TABLE `tick`` space.dot` (value INT);
INSERT INTO `tick`` space.dot` VALUES (42);
CREATE VIEW tiny_view AS SELECT n FROM million_rows WHERE n <= 3;
UPDATE performance_schema.setup_consumers SET ENABLED='YES'
WHERE NAME IN ('events_statements_current','events_statements_history','events_statements_history_long');
