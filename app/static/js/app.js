// Planner Dashboard PRO - Main JavaScript

// Initialize tooltips
$(document).ready(function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-hide alerts
    setTimeout(function() {
        $('.alert:not(.alert-permanent)').alert('close');
    }, 5000);
});

// Global sync function
function syncData() {
    Swal.fire({
        title: 'Sincronizando...',
        text: 'Por favor, aguarde enquanto sincronizamos os dados com o Microsoft Planner',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    $.post('/api/sync', function(data) {
        if (data.success) {
            Swal.fire({
                icon: 'success',
                title: 'Sincronização Completa!',
                html: `
                    <div class="text-start">
                        <p>${data.message}</p>
                        <ul class="list-unstyled">
                            <li><i class="fas fa-users text-primary me-2"></i> Grupos: ${data.result.stats.groups}</li>
                            <li><i class="fas fa-project-diagram text-success me-2"></i> Planners: ${data.result.stats.planners}</li>
                            <li><i class="fas fa-tasks text-info me-2"></i> Tarefas: ${data.result.stats.tasks}</li>
                        </ul>
                    </div>
                `,
                showConfirmButton: true,
                confirmButtonText: 'OK'
            }).then(() => {
                location.reload();
            });
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Erro na Sincronização',
                text: data.error || 'Erro desconhecido'
            });
        }
    }).fail(function(xhr) {
        Swal.fire({
            icon: 'error',
            title: 'Erro de Conexão',
            text: 'Não foi possível conectar ao servidor'
        });
    });
}

// Toggle task favorite status
function toggleFavorite(plannerId, element) {
    const isFavorite = $(element).find('i').hasClass('fas');
    
    $.ajax({
        url: `/api/planners/${plannerId}/favorite`,
        type: 'POST',
        data: JSON.stringify({ favorite: !isFavorite }),
        contentType: 'application/json',
        success: function(data) {
            if (data.success) {
                if (data.favorite) {
                    $(element).find('i').removeClass('far').addClass('fas');
                } else {
                    $(element).find('i').removeClass('fas').addClass('far');
                }
            }
        }
    });
}

// Show planner statistics
function showStats(plannerId) {
    $.get(`/api/planners/${plannerId}/stats`, function(data) {
        if (data.success) {
            Swal.fire({
                title: data.planner.title,
                html: `
                    <div class="text-start">
                        <div class="row mb-3">
                            <div class="col-6">
                                <div class="text-center p-3 bg-light rounded">
                                    <h3 class="mb-0">${data.planner.total_tasks}</h3>
                                    <small class="text-muted">Total de Tarefas</small>
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="text-center p-3 bg-light rounded">
                                    <h3 class="mb-0">${data.planner.completion_rate.toFixed(1)}%</h3>
                                    <small class="text-muted">Taxa de Conclusão</small>
                                </div>
                            </div>
                        </div>
                        
                        <h6 class="mb-2">Distribuição por Status:</h6>
                        <ul class="list-unstyled">
                            ${data.status_stats.map(stat => `
                                <li class="d-flex justify-content-between mb-1">
                                    <span>${stat.status || 'Sem status'}:</span>
                                    <span class="fw-bold">${stat.count}</span>
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                `,
                showConfirmButton: false,
                showCloseButton: true,
                width: 500
            });
        }
    });
}

// Format date
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('pt-BR');
}

// Format datetime
function formatDateTime(dateTimeString) {
    if (!dateTimeString) return '';
    const date = new Date(dateTimeString);
    return date.toLocaleString('pt-BR');
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        Swal.fire({
            icon: 'success',
            title: 'Copiado!',
            text: 'Texto copiado para a área de transferência',
            timer: 1500,
            showConfirmButton: false
        });
    });
}

// Load notifications count
function loadNotificationCount() {
    $.get('/api/notifications/unread', function(data) {
        if (data.success) {
            const count = data.count || 0;
            const badge = $('#notification-badge');
            
            if (count > 0) {
                badge.text(count).show();
            } else {
                badge.hide();
            }
        }
    });
}

// Mark notification as read
function markNotificationRead(notificationId) {
    $.post(`/api/notifications/${notificationId}/read`, function(data) {
        if (data.success) {
            $(`#notification-${notificationId}`).removeClass('unread');
            loadNotificationCount();
        }
    });
}

// Keyboard shortcuts
$(document).on('keydown', function(e) {
    // Ctrl + S = Sync
    if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        syncData();
    }
    
    // Ctrl + F = Focus search
    if (e.ctrlKey && e.key === 'f') {
        e.preventDefault();
        $('input[name="search"]').focus();
    }
    
    // Ctrl + H = Go home
    if (e.ctrlKey && e.key === 'h') {
        e.preventDefault();
        window.location.href = '/dashboard';
    }
});

// Export data
function exportData(format) {
    const filters = {};
    $('form#filterForm').serializeArray().forEach(item => {
        if (item.value) {
            filters[item.name] = item.value;
        }
    });
    
    $.ajax({
        url: '/api/export/tasks',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            format: format,
            filters: filters
        }),
        success: function(data, status, xhr) {
            if (format === 'excel') {
                // Create download link
                const blob = new Blob([data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `tarefas_${new Date().toISOString().slice(0,10)}.xlsx`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            }
        },
        error: function(xhr) {
            Swal.fire({
                icon: 'error',
                title: 'Erro na Exportação',
                text: xhr.responseJSON?.error || 'Erro ao exportar dados'
            });
        }
    });
}

// Auto-refresh if enabled
if (typeof autoRefreshInterval !== 'undefined' && autoRefreshInterval > 0) {
    setInterval(function() {
        if (document.visibilityState === 'visible') {
            location.reload();
        }
    }, autoRefreshInterval * 1000);
}

// Initialize when page loads
$(document).ready(function() {
    // Load notification count every 30 seconds
    loadNotificationCount();
    setInterval(loadNotificationCount, 30000);
    
    // Initialize DataTables if present
    if ($.fn.DataTable) {
        $('table.data-table').DataTable({
            language: {
                url: '//cdn.datatables.net/plug-ins/1.13.4/i18n/pt-BR.json'
            },
            pageLength: 25,
            responsive: true
        });
    }
});