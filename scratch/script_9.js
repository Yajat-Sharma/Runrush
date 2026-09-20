
    async function handleRunSubmit(event) {
      const dateInput = document.getElementById('dateInput');
      const distanceInput = document.getElementById('distanceInput');
      const minutesInput = document.getElementById('minutes');
      const notesInput = document.querySelector('textarea[name="notes"]');
      const formError = document.getElementById('formError');

      // Get values
      const date = dateInput?.value || new Date().toISOString().split('T')[0];
      const distance = parseFloat(distanceInput?.value);
      const time = parseFloat(minutesInput?.value);
      const notes = notesInput?.value || '';

      // Client-side validation (same as before)
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      if (dateInput && dateInput.value) {
        const selectedDate = new Date(dateInput.value + 'T00:00:00');
        if (selectedDate > today) {
          event.preventDefault();
          formError.textContent = 'You cannot log runs for future dates.';
          formError.style.display = 'block';
          return false;
        }
      }

      if (isNaN(distance) || distance <= 0) {
        event.preventDefault();
        formError.textContent = 'Distance must be greater than 0 km.';
        formError.style.display = 'block';
        return false;
      }

      if (isNaN(time) || time <= 0) {
        event.preventDefault();
        formError.textContent = 'Duration must be greater than 0 minutes.';
        formError.style.display = 'block';
        return false;
      }

      const pace = time / distance;
      if (pace > 30 || pace < 2) {
        event.preventDefault();
        formError.textContent = 'Pace seems unrealistic. Please check your distance and time.';
        formError.style.display = 'block';
        return false;
      }

      // Check if offline
      if (!navigator.onLine) {
        event.preventDefault();

        try {
          // Save to IndexedDB
          const offlineRun = await saveOfflineRun({
            date: date,
            distance: distance,
            time: time,
            notes: notes
          });

          // Show success message
          formError.className = 'text-success mt-2';
          formError.textContent = 'Run saved offline. Will sync when online.';
          formError.style.display = 'block';

          // Update UI
          await updateOfflineRunsUI();

          // Close modal after 2 seconds
          setTimeout(() => {
            const modal = bootstrap.Modal.getInstance(document.getElementById('addRunModal'));
            if (modal) modal.hide();

            // Reset form
            document.getElementById('addRunForm').reset();
            formError.style.display = 'none';
            formError.className = 'text-danger mt-2';
          }, 2000);

        } catch (error) {
          console.error('Error saving offline run:', error);
          formError.textContent = 'Failed to save offline run: ' + error.message;
          formError.style.display = 'block';
        }

        return false;
      }

      // Online - allow normal form submission
      formError.style.display = 'none';
      return true;
    }
  