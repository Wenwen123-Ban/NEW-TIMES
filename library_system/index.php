<?php
require_once 'db.php';

$books = [];
$res = $conn->query('SELECT book_id, title, author, status FROM books ORDER BY title ASC LIMIT 500');
while ($row = $res->fetch_assoc()) {
    $books[] = $row;
}
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>LBAS | Secured Mobile Access</title>
  <link rel="stylesheet" href="../static/css/LBAS.css">
  <script src="../static/js/LBAS.js" defer></script>
</head>
<body class="main-wrapper">
  <header class="main-header"><h1>Library Borrowing and Assistance System</h1></header>
  <main class="content">
    <h3>Available Books</h3>
    <div class="book-grid">
      <?php foreach ($books as $book): ?>
        <button type="button" class="book-card" onclick="document.getElementById('book_id').value='<?= (int)$book['book_id'] ?>';document.getElementById('selectedBook').textContent='<?= htmlspecialchars($book['title']) ?>';">
          <strong><?= htmlspecialchars($book['title']) ?></strong><br>
          <small><?= htmlspecialchars($book['author']) ?></small><br>
          <span><?= htmlspecialchars($book['status']) ?></span>
        </button>
      <?php endforeach; ?>
    </div>

    <section id="reserveModal" class="custom-modal" style="display:block; margin-top:20px;">
      <h4>Reserve Book</h4>
      <p id="selectedBook">Select a book above.</p>
      <form method="post" action="reserve.php">
        <input type="hidden" id="book_id" name="book_id" required>
        <input type="text" name="student_id" placeholder="Student ID" required>
        <input type="date" name="pickup_date" required>
        <button type="submit">CONFIRM</button>
      </form>
      <?php if (isset($_GET['msg'])): ?><p><?= htmlspecialchars($_GET['msg']) ?></p><?php endif; ?>
    </section>
  </main>
</body>
</html>
