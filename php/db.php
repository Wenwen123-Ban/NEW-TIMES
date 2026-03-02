<?php
// Migrated from Admin_page1.py JSON storage: central MySQL connection + schema bootstrap.
$host = 'localhost';
$user = 'root';
$pass = '';
$dbName = 'library_system';

$conn = new mysqli($host, $user, $pass);
if ($conn->connect_error) {
    die('Connection failed: ' . $conn->connect_error);
}

$conn->query("CREATE DATABASE IF NOT EXISTS `$dbName` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
$conn->select_db($dbName);
$conn->set_charset('utf8mb4');

$conn->query("CREATE TABLE IF NOT EXISTS students (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(50) DEFAULT 'General'
)");

$conn->query("CREATE TABLE IF NOT EXISTS books (
    book_id INT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    author VARCHAR(200) DEFAULT 'Unknown',
    status VARCHAR(20) DEFAULT 'Available'
)");

$conn->query("CREATE TABLE IF NOT EXISTS reservations (
    res_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20) NOT NULL,
    book_id INT NOT NULL,
    pickup_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_by VARCHAR(50) NULL,
    approved_at TIMESTAMP NULL,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE
)");

$conn->query("CREATE TABLE IF NOT EXISTS blocked_dates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL,
    reason VARCHAR(200) DEFAULT 'Unavailable',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)");

// Needed for secure admin auth in admin_actions.php (hashes; migrated from admins.json plaintext passwords).
$conn->query("CREATE TABLE IF NOT EXISTS admins (
    username VARCHAR(50) PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'Staff'
)");

function seed_from_json_if_needed(mysqli $conn): void {
    $count = (int)$conn->query('SELECT COUNT(*) AS c FROM students')->fetch_assoc()['c'];
    if ($count > 0) {
        return;
    }

    $root = dirname(__DIR__);

    $usersPath = $root . '/users.json';
    if (file_exists($usersPath)) {
        $users = json_decode((string)file_get_contents($usersPath), true) ?: [];
        $stmt = $conn->prepare('INSERT IGNORE INTO students (id, name, department) VALUES (?, ?, ?)');
        foreach ($users as $u) {
            $id = substr((string)($u['school_id'] ?? ''), 0, 20);
            if ($id === '') continue;
            $name = substr((string)($u['name'] ?? 'Unknown Student'), 0, 100);
            $dept = substr((string)($u['category'] ?? 'General'), 0, 50);
            $stmt->bind_param('sss', $id, $name, $dept);
            $stmt->execute();
        }
        $stmt->close();
    }

    $booksPath = $root . '/books.json';
    if (file_exists($booksPath)) {
        $books = json_decode((string)file_get_contents($booksPath), true) ?: [];
        $stmt = $conn->prepare('INSERT IGNORE INTO books (book_id, title, author, status) VALUES (?, ?, ?, ?)');
        foreach ($books as $b) {
            $rawNo = preg_replace('/\D+/', '', (string)($b['book_no'] ?? ''));
            $id = (int)$rawNo;
            if ($id <= 0) continue;
            $title = substr((string)($b['title'] ?? 'Untitled'), 0, 200);
            $author = substr((string)($b['author'] ?? 'Unknown'), 0, 200);
            $status = (strcasecmp((string)($b['status'] ?? ''), 'Borrowed') === 0) ? 'Borrowed' : 'Available';
            $stmt->bind_param('isss', $id, $title, $author, $status);
            $stmt->execute();
        }
        $stmt->close();
    }

    $txnPath = $root . '/transactions.json';
    if (file_exists($txnPath)) {
        $txns = json_decode((string)file_get_contents($txnPath), true) ?: [];
        $stmt = $conn->prepare('INSERT INTO reservations (student_id, book_id, pickup_date, status, approved_by, approved_at) VALUES (?, ?, ?, ?, ?, ?)');
        foreach ($txns as $t) {
            $sid = substr((string)($t['school_id'] ?? ''), 0, 20);
            $bid = (int)preg_replace('/\D+/', '', (string)($t['book_no'] ?? '0'));
            if ($sid === '' || $bid <= 0) continue;

            $dateRaw = (string)($t['pickup_schedule'] ?? $t['date'] ?? '');
            $date = date('Y-m-d', strtotime($dateRaw ?: 'now'));

            $legacy = strtolower((string)($t['status'] ?? 'Reserved'));
            $status = 'PENDING';
            $approvedBy = null;
            $approvedAt = null;
            if ($legacy === 'borrowed' || $legacy === 'returned' || $legacy === 'converted') {
                $status = 'APPROVED';
                $approvedBy = 'migrated-admin';
                $approvedAt = date('Y-m-d H:i:s');
            } elseif (in_array($legacy, ['cancelled', 'expired', 'unavailable'], true)) {
                $status = 'CANCELLED';
            }
            // Ensure referential integrity from migrated Python JSON dataset.
            $conn->query("INSERT IGNORE INTO students (id, name, department) VALUES ('" . $conn->real_escape_string($sid) . "', 'Migrated Student', 'General')");
            $conn->query("INSERT IGNORE INTO books (book_id, title, author, status) VALUES ($bid, 'Migrated Book $bid', 'Unknown', 'Available')");

            $stmt->bind_param('sissss', $sid, $bid, $date, $status, $approvedBy, $approvedAt);
            $stmt->execute();
        }
        $stmt->close();
    }

    $blockedPath = $root . '/system_config.json';
    if (file_exists($blockedPath)) {
        // No blocked date array existed in old config; insert one deterministic maintenance day for testing.
        $conn->query("INSERT IGNORE INTO blocked_dates (date, reason) VALUES (DATE_ADD(CURDATE(), INTERVAL 1 DAY), 'Migrated maintenance day')");
    }

    $adminsPath = $root . '/admins.json';
    if (file_exists($adminsPath)) {
        $admins = json_decode((string)file_get_contents($adminsPath), true) ?: [];
        $stmt = $conn->prepare('INSERT IGNORE INTO admins (username, password_hash, role) VALUES (?, ?, ?)');
        foreach ($admins as $a) {
            $username = substr((string)($a['school_id'] ?? ''), 0, 50);
            if ($username === '') continue;
            $passwordHash = password_hash((string)($a['password'] ?? 'admin'), PASSWORD_DEFAULT);
            $role = substr((string)($a['role'] ?? 'Staff'), 0, 50);
            $stmt->bind_param('sss', $username, $passwordHash, $role);
            $stmt->execute();
        }
        $stmt->close();
    }

    $conn->query("INSERT IGNORE INTO admins (username, password_hash, role) VALUES ('admin', '" . $conn->real_escape_string(password_hash('admin', PASSWORD_DEFAULT)) . "', 'System')");
}

seed_from_json_if_needed($conn);
