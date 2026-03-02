<?php
require_once 'db.php';
$pending = $conn->query("SELECT res_id FROM reservations WHERE status='PENDING' LIMIT 1")->fetch_assoc();
if (!$pending) {
    echo "No pending reservations to approve\n";
    exit(0);
}
session_start();
$_SESSION['admin_user'] = 'admin';
$_SERVER['REQUEST_METHOD'] = 'POST';
$_POST = ['action' => 'approve', 'res_id' => $pending['res_id']];
require 'admin_actions.php';
