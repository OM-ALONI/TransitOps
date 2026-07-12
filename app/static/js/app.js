(function() {
    'use strict';

    // we store theme in localStorage so it sticks around
    // found this trick on a medium article, honestly surprised it works this well
    var storedTheme = localStorage.getItem('theme') || 'dark';
    // console.log('theme loaded:', storedTheme);  // keep for debugging
    document.documentElement.setAttribute('data-theme', storedTheme);
    updateThemeIcon(storedTheme);

    var themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            var current = document.documentElement.getAttribute('data-theme');
            var next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
            updateThemeIcon(next);
        });
    }

    function updateThemeIcon(theme) {
        var icon = document.getElementById('themeIcon');
        if (icon) {
            if (theme === 'dark') {
                icon.className = 'bi bi-sun-fill';
            } else {
                icon.className = 'bi bi-moon-fill';
            }
        }
    }

    var alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = bootstrap.Alert.getInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    });

    Chart.defaults.color = getComputedStyle(document.documentElement)
        .getPropertyValue('--text-secondary').trim() || '#64748B';
    Chart.defaults.borderColor = getComputedStyle(document.documentElement)
        .getPropertyValue('--border-color').trim() || '#E2E8F0';
    Chart.defaults.font.family = "'Segoe UI', system-ui, -apple-system, sans-serif";
    Chart.defaults.font.size = 12;

    animateKpiCounters();

    initFormLoadingState();

    initToastContainer();

    function animateKpiCounters() {
        var counters = document.querySelectorAll('.kpi-value');
        counters.forEach(function(el) {
            var targetText = el.textContent.trim();
            var isPercent = targetText.endsWith('%');
            var isDecimal = targetText.includes('.');
            var target = parseFloat(targetText.replace('%', '').replace(/,/g, ''));
            if (isNaN(target)) return;

            var duration = 1000;
            var start = performance.now();
            var initial = 0;

            function update(now) {
                var elapsed = now - start;
                var progress = Math.min(elapsed / duration, 1);
                var eased = 1 - Math.pow(1 - progress, 3);
                var current = initial + (target - initial) * eased;

                if (isDecimal) {
                    el.textContent = current.toFixed(1);
                } else {
                    el.textContent = Math.round(current);
                }

                if (isPercent) {
                    el.textContent += '%';
                }

                if (progress < 1) {
                    requestAnimationFrame(update);
                } else {
                    el.textContent = targetText;
                }
            }

            requestAnimationFrame(update);
        });
    }

    function initFormLoadingState() {
        document.querySelectorAll('form').forEach(function(form) {
            form.addEventListener('submit', function(e) {
                var btn = form.querySelector('button[type="submit"]');
                if (!btn) return;
                if (!form.checkValidity()) return;

                var btnText = btn.querySelector('.btn-text');
                var spinner = btn.querySelector('.spinner-border');
                if (btnText && spinner) {
                    btnText.classList.add('d-none');
                    spinner.classList.remove('d-none');
                }
                btn.disabled = true;
            });
        });
    }

    function initToastContainer() {
        var container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(container);
        }
    }

    window.showToast = function(message, type) {
        type = type || 'info';
        var bgClass = type === 'success' ? 'bg-success text-white' :
                       type === 'danger' ? 'bg-danger text-white' :
                       type === 'warning' ? 'bg-warning' : 'bg-info text-white';

        var container = document.getElementById('toastContainer');
        var toastEl = document.createElement('div');
        toastEl.className = 'toast align-items-center border-0 ' + bgClass;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        toastEl.innerHTML = '<div class="d-flex"><div class="toast-body fw-semibold">' +
            message + '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';

        container.appendChild(toastEl);
        var bsToast = new bootstrap.Toast(toastEl, { delay: 4000 });
        bsToast.show();

        toastEl.addEventListener('hidden.bs.toast', function() {
            toastEl.remove();
        });
    };

})();
