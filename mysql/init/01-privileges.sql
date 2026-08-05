-- Least-privilege grants for the application user.
-- Note: This runs only on the first MySQL initialization.

CREATE USER IF NOT EXISTS 'dms_user'@'%' IDENTIFIED BY 'k5Tn9Wb2Qv7Mx4Lc8Ya1Jp6Zr3Hd0Gs9Vu2Ef5Bn8Ct';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'dms_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, TRIGGER
  ON distribution_management_system.* TO 'dms_user'@'%';
FLUSH PRIVILEGES;
