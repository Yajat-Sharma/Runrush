
        document.getElementById('weeklyLeaderboardCard').addEventListener('click', function () {
          const rest = document.getElementById('lb-rest');
          const chevron = document.getElementById('lbChevron');
          if (rest) {
            rest.classList.toggle('d-none');
            chevron.classList.toggle('rotated');
          }
        });
      