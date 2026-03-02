<?php
require_once 'db.php';
$res = $conn->query('SELECT DATABASE() AS db, (SELECT COUNT(*) FROM students) AS students, (SELECT COUNT(*) FROM books) AS books');
print_r($res->fetch_assoc());
