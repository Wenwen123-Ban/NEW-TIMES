<?php
require_once 'db.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'message' => 'Method not allowed']);
    exit;
}

$studentId = trim($_POST['student_id'] ?? '');
$bookId = (int)($_POST['book_id'] ?? 0);
$pickupDate = trim($_POST['pickup_date'] ?? '');

function fail($message) {
    if (isset($_SERVER['HTTP_ACCEPT']) && str_contains($_SERVER['HTTP_ACCEPT'], 'application/json')) {
        header('Content-Type: application/json');
        echo json_encode(['success' => false, 'message' => $message]);
    } else {
        header('Location: index.php?msg=' . urlencode($message));
    }
    exit;
}

if ($studentId === '' || $bookId <= 0 || $pickupDate === '') fail('Missing fields.');

// Migrated backend rule from Admin_page1.py reservation checks: student must exist.
$stmt = $conn->prepare('SELECT id FROM students WHERE id = ?');
$stmt->bind_param('s', $studentId);
$stmt->execute();
if (!$stmt->get_result()->fetch_assoc()) fail('Student ID does not exist.');
$stmt->close();

$stmt = $conn->prepare('SELECT book_id, status FROM books WHERE book_id = ?');
$stmt->bind_param('i', $bookId);
$stmt->execute();
$book = $stmt->get_result()->fetch_assoc();
$stmt->close();
if (!$book) fail('Book does not exist.');
if (strcasecmp($book['status'], 'Available') !== 0) fail('Book is not available.');

$ts = strtotime($pickupDate);
if ($ts === false) fail('Invalid pickup date.');
$weekday = (int)date('N', $ts);
if ($weekday >= 6) fail('Pickup date cannot be weekend.');

$stmt = $conn->prepare('SELECT id FROM blocked_dates WHERE date = ?');
$stmt->bind_param('s', $pickupDate);
$stmt->execute();
if ($stmt->get_result()->fetch_assoc()) fail('Pickup date is blocked by admin.');
$stmt->close();

$stmt = $conn->prepare("SELECT COUNT(*) AS c FROM reservations WHERE student_id = ? AND status = 'PENDING'");
$stmt->bind_param('s', $studentId);
$stmt->execute();
$pendingCount = (int)$stmt->get_result()->fetch_assoc()['c'];
$stmt->close();
if ($pendingCount >= 3) fail('Maximum 3 active reservations reached.');

$stmt = $conn->prepare("SELECT COUNT(*) AS c FROM reservations WHERE student_id = ? AND status = 'APPROVED'");
$stmt->bind_param('s', $studentId);
$stmt->execute();
$borrowCount = (int)$stmt->get_result()->fetch_assoc()['c'];
$stmt->close();
if ($borrowCount >= 3) fail('Maximum 3 active borrows reached.');

$stmt = $conn->prepare("SELECT res_id FROM reservations WHERE student_id = ? AND book_id = ? AND status IN ('PENDING','APPROVED')");
$stmt->bind_param('si', $studentId, $bookId);
$stmt->execute();
if ($stmt->get_result()->fetch_assoc()) fail('Duplicate reservation for this book is not allowed.');
$stmt->close();

$stmt = $conn->prepare("INSERT INTO reservations (student_id, book_id, pickup_date, status) VALUES (?, ?, ?, 'PENDING')");
$stmt->bind_param('sis', $studentId, $bookId, $pickupDate);
$ok = $stmt->execute();
$stmt->close();

if (!$ok) fail('Unable to create reservation.');

if (isset($_SERVER['HTTP_ACCEPT']) && str_contains($_SERVER['HTTP_ACCEPT'], 'application/json')) {
    header('Content-Type: application/json');
    echo json_encode(['success' => true, 'message' => 'Reservation submitted.']);
} else {
    header('Location: index.php?msg=' . urlencode('Reservation submitted.'));
}
