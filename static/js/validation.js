const OFFER_NUMBER_PATTERN = /^\d{3}\/\d{2}$/;

function validateOfferNumber(value) {
    return OFFER_NUMBER_PATTERN.test(value);
}

function validateForm() {
    const offerNumber = document.getElementById('offer_number');
    const offerTitle = document.getElementById('offer_title');
    const leaderSelect = document.getElementById('leader_select');
    const dateInput = document.getElementById('date');

    if (offerNumber && !validateOfferNumber(offerNumber.value)) {
        alert(getTranslation('error_offer_number_format') || 'Format: 123/45');
        offerNumber.focus();
        return false;
    }

    if (offerTitle && !offerTitle.value.trim()) {
        alert(getTranslation('error_required') || 'Pflichtfeld');
        offerTitle.focus();
        return false;
    }

    if (leaderSelect && !leaderSelect.value) {
        alert(getTranslation('please_select') || 'Bitte auswaehlen');
        leaderSelect.focus();
        return false;
    }

    if (dateInput && !dateInput.value) {
        alert(getTranslation('error_required') || 'Pflichtfeld');
        dateInput.focus();
        return false;
    }

    if (dateInput && dateInput.value) {
        const selectedDate = new Date(dateInput.value);
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        if (selectedDate > today) {
            alert(getTranslation('error_future_date') || 'Datum darf nicht in Zukunft liegen');
            dateInput.focus();
            return false;
        }
    }

    return true;
}

function validateFeedbackForm() {
    const questions = document.querySelectorAll('.question-group');
    for (const group of questions) {
        const radios = group.querySelectorAll('input[type="radio"]');
        const checked = group.querySelector('input[type="radio"]:checked');
        if (radios.length > 0 && !checked) {
            alert(getTranslation('error_required') || 'Bitte alle Fragen beantworten');
            return false;
        }
    }
    return true;
}

function getTranslation(key) {
    const translations = {
        'de': {
            'error_offer_number_format': 'Format: 123/45',
            'error_project_number_format': 'Format: 123/45',
            'error_required': 'Pflichtfeld',
            'please_select': 'Bitte auswaehlen',
            'error_future_date': 'Datum darf nicht in Zukunft liegen'
        },
        'en': {
            'error_offer_number_format': 'Format: 123/45',
            'error_project_number_format': 'Format: 123/45',
            'error_required': 'Required field',
            'please_select': 'Please select',
            'error_future_date': 'Date cannot be in the future'
        }
    };

    const lang = document.documentElement.lang || 'de';
    return translations[lang]?.[key] || key;
}

function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function() {
            showCopyFeedback();
        }).catch(function() {
            fallbackCopy(text);
        });
    } else {
        fallbackCopy(text);
    }
}

function fallbackCopy(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    document.body.appendChild(textArea);
    textArea.select();
    try {
        document.execCommand('copy');
        showCopyFeedback();
    } catch (err) {
        console.error('Failed to copy:', err);
    }
    document.body.removeChild(textArea);
}

function showCopyFeedback() {
    var btn = document.getElementById('copyBtn');
    if (!btn) return;
    var origBg = btn.style.background || '';
    var origText = btn.textContent;
    var lang = document.documentElement.lang || 'de';
    btn.style.background = '#28a745';
    btn.textContent = lang === 'en' ? 'Copied!' : 'Kopiert!';
    setTimeout(function() {
        btn.style.background = origBg;
        btn.textContent = origText;
    }, 2000);
}

function setupNumberInput(inputId) {
    var input = document.getElementById(inputId);
    if (input) {
        input.addEventListener('input', function(e) {
            var value = e.target.value;
            // Only auto-insert slash when typing forward (not deleting)
            if (e.inputType && e.inputType.startsWith('delete')) return;
            if (value.length === 3 && !value.includes('/')) {
                e.target.value = value + '/';
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    setupNumberInput('offer_number');
    setupNumberInput('project_number');

    const forms = document.querySelectorAll('form');
    for (const form of forms) {
        if (form.id === 'feedback-form') {
            form.addEventListener('submit', function(e) {
                if (!validateFeedbackForm()) {
                    e.preventDefault();
                }
            });
        }
    }
});
