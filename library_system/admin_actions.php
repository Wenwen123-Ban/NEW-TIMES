<?php
require_once 'db.php';
session_start();

$action = $_POST['action'] ?? '';

function done($msg) {
    header('Location: admin.php?msg=' . urlencode($msg));
    exit;
}

$conn->query('DELETE FROM blocked_dates WHERE date < CURDATE()');

if ($action === 'login') {
    $username = trim($_POST['username'] ?? '');
    $password = (string)($_POST['password'] ?? '');
    $stmt = $conn->prepare('SELECT username, password_hash FROM admins WHERE username = ?');
    $stmt->bind_param('s', $username);
    $stmt->execute();
    $admin = $stmt->get_result()->fetch_assoc();
    $stmt->close();

    if (!$admin || !password_verify($password, $admin['password_hash'])) {
        done('Invalid admin credentials.');
    }
    $_SESSION['admin_user'] = $admin['username'];
    done('Admin logged in.');
}

if (!isset($_SESSION['admin_user'])) {
    done('Admin authentication required.');
}

if ($action === 'approve') {
    $resId = (int)($_POST['res_id'] ?? 0);
    $stmt = $conn->prepare("UPDATE reservations SET status='APPROVED', approved_by=?, approved_at=NOW() WHERE res_id=? AND status='PENDING'");
    $stmt->bind_param('si', $_SESSION['admin_user'], $resId);
    $stmt->execute();
    $stmt->close();

    $stmt = $conn->prepare('SELECT book_id FROM reservations WHERE res_id = ?');
    $stmt->bind_param('i', $resId);
    $stmt->execute();
    $row = $stmt->get_result()->fetch_assoc();
    $stmt->close();
    if ($row) {
        $bookId = (int)$row['book_id'];
        $stmt = $conn->prepare("UPDATE books SET status='Borrowed' WHERE book_id = ?");
        $stmt->bind_param('i', $bookId);
        $stmt->execute();
        $stmt->close();
    }
    done('Reservation approved.');
}

if ($action === 'add_blocked_date') {
    $date = trim($_POST['date'] ?? '');
    $reason = trim($_POST['reason'] ?? 'Unavailable');
    $stmt = $conn->prepare('INSERT INTO blocked_dates (date, reason) VALUES (?, ?)');
    $stmt->bind_param('ss', $date, $reason);
    $stmt->execute();
    $stmt->close();
    done('Blocked date added.');
}

if ($action === 'remove_blocked_date') {
    $id = (int)($_POST['id'] ?? 0);
    $stmt = $conn->prepare('DELETE FROM blocked_dates WHERE id = ?');
    $stmt->bind_param('i', $id);
    $stmt->execute();
    $stmt->close();
    done('Blocked date removed.');
}

done('Unknown action.');
