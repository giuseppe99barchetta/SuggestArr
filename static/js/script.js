document.addEventListener('DOMContentLoaded', function () {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Check if all fields are filled at page load
    checkFormFields();

    // Add event listeners to form fields to disable the Force Run button when modified
    const formFields = document.querySelectorAll('input');
    formFields.forEach(field => {
        field.addEventListener('input', function() {
            document.getElementById('run-now').style.display = 'none'; // Hide the button on any modification
        });
    });

    // Handle form submission with AJAX
    const form = document.querySelector('form');
    form.addEventListener('submit', function (event) {
        event.preventDefault(); // Prevent default form submission
        const formData = new FormData(this);

        fetch(this.action, {
            method: 'POST',
            body: formData,
        })
        .then(response => {
            if (response.ok) {
                showToast("Configuration saved successfully!", 'toast-config');
                document.getElementById('run-now').style.display = 'block'; // Show Force Run button
            } else {
                showToast("Error saving configuration!", 'toast-config');
            }
        })
        .catch((error) => {
            console.error('Error:', error);
            showToast("An error occurred while saving the configuration!", 'toast-config');
        });
    });

    // Handle Force Run button click
    document.getElementById('run-now').addEventListener('click', function() {
        showToast("Process started in background.", 'toast-run');
        fetch('/run_now', {
            method: 'POST',
        })
        .then(response => {
            if (response.ok) {
                showToast("Process completed! Check Jellyseer for new Movie or TV Show!", 'toast-run');
            } else {
                showToast("Error occurred during the process!", 'toast-run');
            }
        })
        .catch((error) => {
            console.error('Error:', error);
            showToast("An error occurred during the process!", 'toast-run');
        });
    });

    // Handle cron input changes
    document.getElementById('CRON_TIMES').addEventListener('input', function () {
        const cronInput = this.value;
        const cronDescriptionElement = document.getElementById('cron-description');
        try {
            const humanReadable = cronstrue.toString(cronInput);
            cronDescriptionElement.textContent = humanReadable;
        } catch (err) {
            console.error(err);
            cronDescriptionElement.textContent = 'Invalid cron expression';
        }
    });
});

// Check if all form fields are filled
function checkFormFields() {
    const requiredFields = ['TMDB_API_KEY', 'JELLYFIN_API_URL', 'JELLYFIN_TOKEN', 'JELLYSEER_API_URL', 'JELLYSEER_TOKEN', 'MAX_SIMILAR_MOVIE', 'MAX_SIMILAR_TV', 'CRON_TIMES'];

    let allFieldsFilled = true;
    requiredFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (!field || field.value.trim() === '') {
            allFieldsFilled = false;
        }
    });

    // Show the Force Run button if all fields are filled
    const runNowButton = document.getElementById('run-now');
    if (allFieldsFilled) {
        runNowButton.style.display = 'block';
    } else {
        runNowButton.style.display = 'none';
    }
}

// Show toast message function
function showToast(message, toast_id) {
    const toast = document.getElementById(toast_id);
    if (!toast) {
        console.error('Toast element not found:', toast_id);
        return;
    }
    toast.textContent = message;
    toast.style.display = 'block';

    setTimeout(() => {
        toast.style.display = 'none';
    }, 5000);
}
