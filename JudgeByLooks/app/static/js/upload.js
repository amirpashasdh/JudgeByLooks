const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

const uploadZone  = document.getElementById('uploadZone');
const fileInput   = document.getElementById('fileInput');
const previewImg  = document.getElementById('previewImg');
const fileInfo    = document.getElementById('fileInfo');
const fileName    = document.getElementById('fileName');
const fileSize    = document.getElementById('fileSize');
const removeBtn   = document.getElementById('removeBtn');
const submitBtn   = document.getElementById('submitBtn');
const uploadError = document.getElementById('uploadError');
const submitError = document.getElementById('submitError');
const uploadView  = document.getElementById('uploadView');
const processingView = document.getElementById('processingView');
const cyclingMsg  = document.getElementById('cyclingMsg');

let selectedFile = null;
let cycleInterval = null;

const MESSAGES = [
  'Reading your colour palette...',
  'Identifying your aesthetic...',
  'Matching to our catalog...',
  'Curating your recommendations...',
  'Almost there...',
];

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function showError(el, msg) {
  el.textContent = msg;
  el.classList.add('visible');
}

function clearError(el) {
  el.textContent = '';
  el.classList.remove('visible');
}

function handleFileSelect(file) {
  clearError(uploadError);
  clearError(submitError);
  if (!file) return;

  if (!ALLOWED_TYPES.includes(file.type)) {
    showError(uploadError, 'Only JPEG, PNG, or WEBP images are accepted.');
    fileInput.value = '';
    return;
  }
  if (file.size > MAX_FILE_SIZE) {
    showError(uploadError, 'File is too large. Maximum size is 10MB.');
    fileInput.value = '';
    return;
  }

  selectedFile = file;

  const reader = new FileReader();
  reader.onload = (e) => {
    previewImg.src = e.target.result;
    uploadZone.classList.add('has-preview');
  };
  reader.readAsDataURL(file);

  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  fileInfo.classList.add('visible');
  submitBtn.disabled = false;
}

function clearSelection() {
  selectedFile = null;
  fileInput.value = '';
  previewImg.src = '';
  uploadZone.classList.remove('has-preview');
  fileInfo.classList.remove('visible');
  submitBtn.disabled = true;
  clearError(uploadError);
  clearError(submitError);
}

function showProcessing() {
  uploadView.style.display = 'none';
  processingView.style.display = 'block';

  let msgIndex = 0;
  function tick() {
    cyclingMsg.classList.remove('visible');
    setTimeout(() => {
      cyclingMsg.textContent = MESSAGES[msgIndex % MESSAGES.length];
      cyclingMsg.classList.add('visible');
      msgIndex++;
    }, 300);
  }
  tick();
  cycleInterval = setInterval(tick, 2200);
}

function showUpload(errorMsg) {
  clearInterval(cycleInterval);
  processingView.style.display = 'none';
  uploadView.style.display = 'block';
  submitBtn.disabled = false;
  if (errorMsg) showError(submitError, errorMsg);
}

async function submitPhoto() {
  if (!selectedFile) return;
  clearError(submitError);
  submitBtn.disabled = true;

  showProcessing();

  const formData = new FormData();
  formData.append('photo', selectedFile);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: formData });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed.' }));
      showUpload(err.detail || 'Something went wrong. Please try again.');
      return;
    }

    const data = await res.json();
    sessionStorage.setItem('session_id', data.session_id);
    sessionStorage.setItem('person_id',  String(data.person_id));
    sessionStorage.setItem('run_folder', data.run_folder);
    sessionStorage.setItem('keywords',   JSON.stringify(data.keywords));

    window.location.href = '/static/results.html';

  } catch (err) {
    showUpload(err.message || 'Network error. Please try again.');
  }
}

uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('drag-over');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});
uploadZone.addEventListener('click', (e) => {
  if (e.target.closest('.upload-label')) return;
  fileInput.click();
});
fileInput.addEventListener('change', (e) => handleFileSelect(e.target.files[0]));
removeBtn.addEventListener('click', clearSelection);
submitBtn.addEventListener('click', submitPhoto);
