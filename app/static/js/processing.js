const MESSAGES = [
  'Reading your colour palette...',
  'Identifying your aesthetic...',
  'Matching to our catalog...',
  'Almost there...',
];

const cyclingMsg = document.getElementById('cyclingMsg');
let msgIndex = 0;
let cycleInterval = null;

function showMessage(text) {
  cyclingMsg.classList.remove('visible');
  setTimeout(() => {
    cyclingMsg.textContent = text;
    cyclingMsg.classList.add('visible');
  }, 300); // fade-out then fade-in
}

function startCycling() {
  showMessage(MESSAGES[msgIndex]);
  cycleInterval = setInterval(() => {
    msgIndex = (msgIndex + 1) % MESSAGES.length;
    showMessage(MESSAGES[msgIndex]);
  }, 1200);
}

window.onload = function () {
  const sessionId = sessionStorage.getItem('session_id');
  const personId  = sessionStorage.getItem('person_id');

  // Guard: if no session data, send back to upload
  if (!sessionId || !personId) {
    window.location.href = '/static/index.html';
    return;
  }

  // Start cycling messages after short delay
  setTimeout(startCycling, 500);

  // Redirect to results after 3s
  setTimeout(() => {
    clearInterval(cycleInterval);
    window.location.href = '/static/results.html';
  }, 3000);
};
