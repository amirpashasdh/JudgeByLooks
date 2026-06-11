const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
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

let selectedFile = null;

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

  // Show image preview inside upload zone
  const reader = new FileReader();
  reader.onload = (e) => {
    previewImg.src = e.target.result;
    uploadZone.classList.add('has-preview');
  };
  reader.readAsDataURL(file);

  // Show file info row
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  fileInfo.classList.add('visible');

  // Enable submit
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

async function submitPhoto() {
  if (!selectedFile) return;

  submitBtn.disabled = true;
  submitBtn.textContent = 'Analysing...';
  clearError(submitError);

  const formData = new FormData();
  formData.append('photo', selectedFile);

  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed.' }));
      throw new Error(err.detail || 'Upload failed.');
    }

    const data = await res.json();

    sessionStorage.setItem('session_id',  data.session_id);
    sessionStorage.setItem('person_id',   String(data.person_id));
    sessionStorage.setItem('run_folder',  data.run_folder);
    sessionStorage.setItem('keywords',    JSON.stringify(data.keywords));

    window.location.href = '/static/processing.html';

  } catch (err) {
    showError(submitError, err.message || 'Something went wrong. Please try again.');
    submitBtn.disabled = false;
    submitBtn.textContent = 'Analyse my style';
  }
}

// ── Drag and drop ──────────────────────────────
uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('drag-over');
});

uploadZone.addEventListener('dragleave', () => {
  uploadZone.classList.remove('drag-over');
});

uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});

// Click on zone (but not on the label/button) opens file picker
uploadZone.addEventListener('click', (e) => {
  if (e.target.closest('.upload-label')) return;
  fileInput.click();
});

// ── File input ─────────────────────────────────
fileInput.addEventListener('change', (e) => {
  handleFileSelect(e.target.files[0]);
});

// ── Remove ─────────────────────────────────────
removeBtn.addEventListener('click', clearSelection);

// ── Submit ─────────────────────────────────────
submitBtn.addEventListener('click', submitPhoto);
