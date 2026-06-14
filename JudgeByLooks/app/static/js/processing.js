const MESSAGES = [
  'Reading your colour palette...',
  'Identifying your aesthetic...',
  'Matching to our catalog...',
  'Curating your recommendations...',
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
  }, 300);
}

function startCycling() {
  showMessage(MESSAGES[msgIndex]);
  cycleInterval = setInterval(() => {
    msgIndex = (msgIndex + 1) % MESSAGES.length;
    showMessage(MESSAGES[msgIndex]);
  }, 2000);
}

function dataURLtoBlob(dataUrl) {
  const [header, b64] = dataUrl.split(',');
  const mime = header.match(/:(.*?);/)[1];
  const binary = atob(b64);
  const arr = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
  return new Blob([arr], { type: mime });
}

window.onload = async function () {
  const photoData = sessionStorage.getItem('pending_photo_data');
  const photoName = sessionStorage.getItem('pending_photo_name') || 'photo.jpg';
  const photoType = sessionStorage.getItem('pending_photo_type') || 'image/jpeg';

  if (!photoData) {
    window.location.href = '/static/index.html';
    return;
  }

  // Clean up the pending keys
  sessionStorage.removeItem('pending_photo_data');
  sessionStorage.removeItem('pending_photo_name');
  sessionStorage.removeItem('pending_photo_type');

  setTimeout(startCycling, 300);

  try {
    const blob = dataURLtoBlob(photoData);
    const formData = new FormData();
    formData.append('photo', blob, photoName);

    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData,
    });

    clearInterval(cycleInterval);

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed.' }));
      sessionStorage.setItem('upload_error', err.detail || 'Something went wrong. Please try again.');
      window.location.href = '/static/index.html';
      return;
    }

    const data = await res.json();
    sessionStorage.setItem('session_id', data.session_id);
    sessionStorage.setItem('person_id',  String(data.person_id));
    sessionStorage.setItem('run_folder', data.run_folder);
    sessionStorage.setItem('keywords',   JSON.stringify(data.keywords));

    window.location.href = '/static/results.html';

  } catch (err) {
    clearInterval(cycleInterval);
    sessionStorage.setItem('upload_error', err.message || 'Network error. Please try again.');
    window.location.href = '/static/index.html';
  }
};
