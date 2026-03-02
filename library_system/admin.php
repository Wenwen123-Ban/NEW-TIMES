<?php
require_once 'db.php';
session_start();

$pending = $conn->query("SELECT r.res_id, r.student_id, r.book_id, r.pickup_date, r.status, s.name, b.title FROM reservations r JOIN students s ON s.id=r.student_id JOIN books b ON b.book_id=r.book_id WHERE r.status='PENDING' ORDER BY r.created_at ASC");
$blocked = $conn->query("SELECT id, date, reason FROM blocked_dates WHERE date >= CURDATE() ORDER BY date ASC");
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LBAS Admin Dashboard</title>
  <link rel="stylesheet" href="../static/css/admin_dashboard.css">
  <script src="../static/js/admin_dashboard.js" defer></script>
</head>
<body>
  <h2>Admin Login</h2>
  <form method="post" action="admin_actions.php">
    <input type="hidden" name="action" value="login">
    <input type="text" name="username" placeholder="Username" required>
    <input type="password" name="password" placeholder="Password" required>
    <button type="submit">Login</button>
  </form>

  <h3>Pending Reservations</h3>
  <table border="1">
    <tr><th>ID</th><th>Student</th><th>Book</th><th>Pickup Date</th><th>Action</th></tr>
    <?php while ($row = $pending->fetch_assoc()): ?>
      <tr>
        <td><?= (int)$row['res_id'] ?></td>
        <td><?= htmlspecialchars($row['student_id'] . ' - ' . $row['name']) ?></td>
        <td><?= htmlspecialchars($row['book_id'] . ' - ' . $row['title']) ?></td>
        <td><?= htmlspecialchars($row['pickup_date']) ?></td>
        <td>
          <form method="post" action="admin_actions.php">
            <input type="hidden" name="action" value="approve">
            <input type="hidden" name="res_id" value="<?= (int)$row['res_id'] ?>">
            <button type="submit">Approve Borrow</button>
          </form>
        </td>
      </tr>
    <?php endwhile; ?>
  </table>

  <h3>Blocked Dates</h3>
  <form method="post" action="admin_actions.php">
    <input type="hidden" name="action" value="add_blocked_date">
    <input type="date" name="date" required>
    <input type="text" name="reason" placeholder="Reason" required>
    <button type="submit">Add blocked date</button>
  </form>

  <ul>
    <?php while ($b = $blocked->fetch_assoc()): ?>
      <li>
        <?= htmlspecialchars($b['date'] . ' - ' . $b['reason']) ?>
        <form method="post" action="admin_actions.php" style="display:inline;">
          <input type="hidden" name="action" value="remove_blocked_date">
          <input type="hidden" name="id" value="<?= (int)$b['id'] ?>">
          <button type="submit">Remove</button>
        </form>
      </li>
    <?php endwhile; ?>
  </ul>
  <?php if (isset($_GET['msg'])): ?><p><?= htmlspecialchars($_GET['msg']) ?></p><?php endif; ?>
</body>
</html>
