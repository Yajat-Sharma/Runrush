(() => {
  'use strict';

  let recognition = null;
  let currentParse = null;
  let isListening = false;
  let recognitionError = false;

  const $ = (id) => document.getElementById(id);

  function setStatus(message, tone = 'muted') {
    const status = $('voiceStatus');
    status.textContent = message;
    status.className = `voice-status text-${tone}`;
  }

  function setListening(listening) {
    isListening = listening;
    const button = $('voiceMicBtn');
    button.classList.toggle('is-listening', listening);
    button.innerHTML = listening
      ? '<i class="fa-solid fa-stop"></i><span>Stop listening</span>'
      : '<i class="fa-solid fa-microphone"></i><span>Start listening</span>';
    button.setAttribute('aria-pressed', String(listening));
  }

  function normalizeSpokenNumbers(text) {
    const numbers = {
      'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
      'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
      'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
      'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
      'eighteen': '18', 'nineteen': '19', 'twenty': '20', 'thirty': '30',
      'forty': '40', 'fifty': '50', 'sixty': '60', 'ninety': '90'
    };
    let normalized = text.toLowerCase().replace(
      /\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|ninety)\b/g,
      (word) => numbers[word]
    );
    normalized = normalized.replace(/\b(20|30|40|50|60|90)\s+([0-9])\b/g, '$1$2');
    return normalized;
  }

  function parseDuration(text) {
    const hour = text.match(/(\d+(?:\.\d+)?)\s*hours?\b/);
    const minute = text.match(/(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)\b/);
    if (hour || minute) {
      return (hour ? parseFloat(hour[1]) * 60 : 0) + (minute ? parseFloat(minute[1]) : 0);
    }
    const clock = text.match(/\b(\d+):(\d{1,2})(?::(\d{1,2}))?\b/);
    if (!clock) return null;
    const first = parseInt(clock[1], 10);
    const second = parseInt(clock[2], 10);
    return clock[3] ? first * 60 + second + parseInt(clock[3], 10) / 60 : first + second / 60;
  }

  function parseVoice(text) {
    const normalized = normalizeSpokenNumbers(text);
    const distanceMatch = normalized.match(/(\d+(?:\.\d+)?)\s*(km|kilomet(?:er|re)s?|k|miles?|mi)\b/);
    const duration = parseDuration(normalized);
    if (!distanceMatch || !duration) {
      currentParse = null;
      $('voiceParsed').hidden = true;
      $('voiceConfirmBtn').disabled = true;
      setStatus('Include distance and duration, for example “5K in 28 minutes”.', 'warning');
      return;
    }

    let distance = parseFloat(distanceMatch[1]);
    if (/miles?|mi\b/.test(distanceMatch[2])) distance *= 1.60934;
    currentParse = {
      distance: Number(distance.toFixed(2)),
      time_minutes: Number(duration.toFixed(2))
    };
    $('vDist').textContent = `${currentParse.distance.toFixed(2)} km`;
    $('vTime').textContent = formatDuration(currentParse.time_minutes);
    $('vPace').textContent = `${(currentParse.time_minutes / currentParse.distance).toFixed(1)} min/km`;
    $('voiceParsed').hidden = false;
    $('voiceConfirmBtn').disabled = false;
    setStatus('Looks good. Review the details before saving.', 'success');
  }

  function formatDuration(minutes) {
    const wholeMinutes = Math.floor(minutes);
    const seconds = Math.round((minutes - wholeMinutes) * 60);
    return seconds ? `${wholeMinutes}m ${seconds}s` : `${wholeMinutes} min`;
  }

  function useManualValues() {
    const distance = parseFloat($('voiceDistance').value);
    const time = parseFloat($('voiceTime').value);
    if (!Number.isFinite(distance) || !Number.isFinite(time)) {
      currentParse = null;
      $('voiceParsed').hidden = true;
      $('voiceConfirmBtn').disabled = true;
      setStatus('Enter both distance and duration to continue.', 'warning');
      return;
    }
    parseVoice(`${distance} km ${time} minutes`);
  }

  function startVoice() {
    if (isListening) {
      recognition?.stop();
      return;
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      $('voiceSupportNotice').hidden = false;
      setStatus('Speech recognition is unavailable. Use the manual fields below.', 'warning');
      return;
    }
    recognition = new SpeechRecognition();
    recognitionError = false;
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
      setListening(true);
      setStatus('Listening… say your distance and duration.', 'primary');
      $('voiceTranscript').textContent = 'Listening…';
    };
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results).map((result) => result[0].transcript).join('');
      $('voiceTranscript').textContent = transcript;
      if (event.results[event.results.length - 1].isFinal) parseVoice(transcript);
    };
    recognition.onerror = (event) => {
      recognitionError = true;
      setListening(false);
      const messages = {
        'not-allowed': 'Microphone permission was denied. Allow it in your browser settings and try again.',
        'service-not-allowed': 'Speech recognition is blocked by this browser. Use the manual fields below.',
        'audio-capture': 'No microphone was found. Check your microphone and try again.',
        'network': 'Speech recognition needs a network connection. Check your connection and try again.'
      };
      setStatus(messages[event.error] || 'Could not hear that. Try again.', 'danger');
    };
    recognition.onend = () => {
      setListening(false);
      if (!currentParse && !recognitionError) setStatus('Ready when you are.', 'muted');
    };
    try {
      recognition.start();
    } catch (error) {
      recognitionError = true;
      setListening(false);
      setStatus('Could not start the microphone. Check browser permission and try again.', 'danger');
    }
  }

  async function confirmVoiceLog() {
    if (!currentParse) return;
    const button = $('voiceConfirmBtn');
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving…';
    try {
      const response = await fetch('/api/voice-quick-log', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
        },
        body: JSON.stringify(currentParse)
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Unable to save this run.');
      bootstrap.Modal.getInstance($('voiceModal'))?.hide();
      if (typeof showToast === 'function') showToast('Run saved!', 'success');
      window.location.reload();
    } catch (error) {
      setStatus(error.message || 'Unable to save this run. Try again.', 'danger');
      button.disabled = false;
      button.textContent = 'Save run';
    }
  }

  function resetVoiceModal() {
    recognition?.stop();
    recognition = null;
    recognitionError = false;
    currentParse = null;
    setListening(false);
    $('voiceTranscript').textContent = 'Say something like “5K in 28 minutes”.';
    $('voiceDistance').value = '';
    $('voiceTime').value = '';
    $('voiceParsed').hidden = true;
    $('voiceConfirmBtn').disabled = true;
    $('voiceConfirmBtn').textContent = 'Save run';
    $('voiceSupportNotice').hidden = true;
    setStatus('Ready when you are.', 'muted');
  }

  window.openVoiceQuickLog = () => bootstrap.Modal.getOrCreateInstance($('voiceModal')).show();
  window.startVoice = startVoice;
  window.useManualValues = useManualValues;
  window.confirmVoiceLog = confirmVoiceLog;
  $('voiceModal')?.addEventListener('hidden.bs.modal', resetVoiceModal);
})();
