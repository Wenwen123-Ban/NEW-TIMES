<?php
require_once 'db.php';
$_SERVER['REQUEST_METHOD'] = 'POST';
$_SERVER['HTTP_ACCEPT'] = 'application/json';
$student = $conn->query('SELECT id FROM students LIMIT 1')->fetch_assoc();
$book = $conn->query("SELECT book_id FROM books WHERE status='Available' LIMIT 1")->fetch_assoc();
$_POST = [
  'student_id' => $student['id'] ?? 'missing',
  'book_id' => $book['book_id'] ?? 0,
  'pickup_date' => date('Y-m-d', strtotime('next monday')),
];
require 'reserve.php';
