/* static/js/app.js */

$(document).ready(function() {
    let currentJobId = null;
    let currentEventSource = null;
    let loggedLinesCount = 0;

    // Injeta estilos CSS customizados para os itens do histórico e transições visuais
    const customStyles = `
        .history-item {
            padding: 10px;
            border-radius: 8px;
            background-color: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .history-item:hover {
            background-color: rgba(0, 240, 255, 0.05) !important;
            border-color: rgba(0, 240, 255, 0.2) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            transform: translateY(-1.5px);
        }
        .history-item.active-item {
            background-color: rgba(0, 240, 255, 0.08) !important;
            border-color: var(--primary-neon) !important;
            box-shadow: 0 0 10px rgba(0, 240, 255, 0.1);
        }
        #btn-logout:hover {
            background-color: var(--danger-red) !important;
            color: #ffffff !important;
            box-shadow: 0 0 10px rgba(255, 62, 62, 0.4);
            transform: translateY(-1px);
        }
    `;
    $("<style>").html(customStyles).appendTo("head");

    // --- EXECUÇÕES DE INICIALIZAÇÃO ---
    checkAuthentication();
    loadCacheTable();
    loadHistoryList();

    // --- VERIFICAÇÃO DE AUTENTICAÇÃO ---
    function checkAuthentication() {
        $.get("/api/auth/me", function(user) {
            $("#username-display span").text(user.username);
        }).fail(function() {
            // Se falhar a requisição de informações do usuário, manda pro login
            window.location.href = "/login";
        });
    }

    // --- CONTROLE DE LOGOUT ---
    $("#btn-logout").click(function(e) {
        e.preventDefault();
        if (confirm("Deseja realmente sair do sistema?")) {
            $.post("/api/auth/logout", function() {
                window.location.href = "/login";
            }).fail(function() {
                alert("Erro ao realizar logout. Tente novamente.");
            });
        }
    });

    // --- CARREGAR HISTÓRICO DE ATENDIMENTOS ---
    function loadHistoryList() {
        $.get("/api/history", function(historyList) {
            const $listBody = $("#history-list-body");
            $listBody.empty();
            
            $("#history-count").text(`${historyList.length} atendimentos`);

            if (!historyList || historyList.length === 0) {
                $listBody.append(`
                    <div style="text-align: center; padding: 20px; font-style: italic; color: var(--text-secondary); font-size: 11px;">
                        Nenhum atendimento no histórico ainda.
                    </div>
                `);
                return;
            }

            historyList.forEach(function(item) {
                const shortInquiry = item.inquiry.length > 40 ? item.inquiry.substring(0, 40) + "..." : item.inquiry;
                let statusLabel = "";
                
                if (item.status === "concluido") {
                    statusLabel = `<span style="color: var(--success-green);"><i class="fa-solid fa-circle" style="font-size: 8px;"></i> Resolvido</span>`;
                } else if (item.status === "erro") {
                    statusLabel = `<span style="color: var(--danger-red);"><i class="fa-solid fa-circle" style="font-size: 8px;"></i> Falhou</span>`;
                } else if (item.status === "aguardando_aprovacao") {
                    statusLabel = `<span style="color: var(--warning-yellow); animation: heartBeat 1.5s infinite ease-in-out;"><i class="fa-solid fa-circle" style="font-size: 8px;"></i> HITL</span>`;
                } else {
                    statusLabel = `<span style="color: var(--primary-neon);"><i class="fa-solid fa-spinner fa-spin" style="font-size: 8px;"></i> Rodando</span>`;
                }

                const createdDate = new Date(item.created_at).toLocaleString('pt-BR', {
                    day: '2-digit',
                    month: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });

                const activeClass = currentJobId === item.job_id ? "active-item" : "";

                $listBody.append(`
                    <div class="history-item ${activeClass}" data-job-id="${item.job_id}">
                        <div style="font-size: 12px; font-weight: 500; color: var(--text-primary); margin-bottom: 4px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
                            ${escapeHtml(shortInquiry)}
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 10px; color: var(--text-secondary);">
                            <span>${createdDate}</span>
                            ${statusLabel}
                        </div>
                    </div>
                `);
            });

            // Adicionar evento de clique para carregar histórico
            $(".history-item").click(function() {
                const jobId = $(this).data("job-id");
                selectHistoryItem(jobId);
            });
        });
    }

    // --- CARREGAR DETALHES DE UM ITEM DO HISTÓRICO ---
    function selectHistoryItem(jobId) {
        currentJobId = jobId;
        
        // Destaca o item selecionado na UI
        $(".history-item").removeClass("active-item");
        $(`.history-item[data-job-id="${jobId}"]`).addClass("active-item");
        
        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
        resetUIForNewRun();
        
        $("#btn-submit").prop("disabled", true);
        appendTerminalLog(`Carregando dados do atendimento #${jobId.substring(0, 8)}...`, "system");

        $.get(`/api/status/${jobId}`, function(job) {
            loggedLinesCount = 0;
            // 1. Atualiza os logs do terminal
            updateTerminalLogs(job.logs);

            // 2. Atualiza os badges de status e pipeline
            updateUIStatus(job.status);
            managePipelineVisuals(job.status);

            // 3. Renderiza rascunhos ou respostas prontas
            if (job.status === "aguardando_aprovacao") {
                showDraftForReview(job.draft);
                enableSubmitButton();
            } else if (job.status === "concluido") {
                showFinalResponse(job.final_response, job.cache_hit);
                enableSubmitButton();
            } else if (job.status === "erro") {
                $("#output-content").html(`
                    <div class="empty-state">
                        <i class="fa-solid fa-circle-exclamation" style="font-size: 48px; color: var(--danger-red);"></i>
                        <h3 style="margin-top: 15px;">Falha na execução dos agentes</h3>
                        <p>Os agentes encontraram uma falha crítica. Verifique os logs no terminal de pensamentos.</p>
                    </div>
                `);
                enableSubmitButton();
            } else {
                // Se o status for de processamento ativo (ex: rodando / triando), re-inicia o Polling de atualização!
                appendTerminalLog("Re-inicializando escuta de processamento ativo em tempo real...", "system");
                startSSEConnection(jobId);
            }
        }).fail(function() {
            appendTerminalLog("❌ Erro ao resgatar detalhes do atendimento selecionado.", "system");
            enableSubmitButton();
        });
    }

    // --- SUBMISSÃO DE DÚVIDA DO CLIENTE ---
    $("#inquiry-form").submit(function(e) {
        e.preventDefault();
        
        const inquiryText = $("#customer-inquiry").val().trim();
        if (!inquiryText) return;

        // Resetar UI
        resetUIForNewRun();
        
        // Bloquear botão de envio
        $("#btn-submit").prop("disabled", true).find("span").text("Processando...");
        $("#btn-submit").find("i").removeClass("fa-circle-play").addClass("fa-spinner fa-spin");

        // Fazer a chamada da API
        $.ajax({
            url: "/api/inquiry",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ inquiry: inquiryText }),
            success: function(response) {
                currentJobId = response.job_id;
                
                if (response.cache_hit) {
                    appendTerminalLog("🎯 CACHE HIT SEMÂNTICO!", "system");
                    appendTerminalLog("Buscando resposta otimizada armazenada...", "system");
                    // Se for cache hit, exibe direto
                    updatePipelineStep("step-cache", "completed");
                    startSSEConnection(currentJobId);
                } else {
                    appendTerminalLog("🚀 CACHE MISS: Dúvida inédita enviada aos agentes.", "system");
                    appendTerminalLog("Higienizando dados pessoais sensíveis (PII)...", "system");
                    appendTerminalLog("Iniciando Crew com Claude 4.5 Haiku, 4.6 Sonnet e 4.7 Opus...", "system");
                    updatePipelineStep("step-cache", "completed");
                    updatePipelineStep("step-triando", "active");
                    startSSEConnection(currentJobId);
                }
                
                // Recarrega a lista do histórico para mostrar a nova dúvida inserida
                loadHistoryList();
            },
            error: function(err) {
                appendTerminalLog("❌ Erro ao enviar solicitação: " + (err.responseJSON?.detail || "Erro desconhecido"), "system");
                enableSubmitButton();
            }
        });
    });

    // --- STREAMING DE STATUS E LOGS VIA SSE ---
    function startSSEConnection(jobId) {
        loggedLinesCount = 0;
        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
        
        appendTerminalLog("Conectando ao canal de streaming em tempo real...", "system");
        
        currentEventSource = new EventSource(`/api/jobs/${jobId}/stream`);
        
        currentEventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === "log") {
                    appendTerminalLog(data.message, data.sender);
                } else if (data.type === "status") {
                    updateUIStatus(data.status);
                    managePipelineVisuals(data.status);
                } else if (data.type === "finished") {
                    updateUIStatus(data.status);
                    managePipelineVisuals(data.status);
                    
                    if (data.status === "aguardando_aprovacao") {
                        showDraftForReview(data.draft);
                        enableSubmitButton();
                        loadHistoryList(); // Atualiza status na lista lateral
                    } else if (data.status === "concluido") {
                        showFinalResponse(data.final_response, data.cache_hit);
                        enableSubmitButton();
                        loadCacheTable(); // Recarregar tabela de cache
                        loadHistoryList(); // Atualiza status na lista lateral
                    } else if (data.status === "erro") {
                        $("#output-content").html(`
                            <div class="empty-state">
                                <i class="fa-solid fa-circle-exclamation" style="font-size: 48px; color: var(--danger-red);"></i>
                                <h3 style="margin-top: 15px;">Falha na execução dos agentes</h3>
                                <p>Os agentes encontraram uma falha crítica. Verifique os logs no terminal de pensamentos.</p>
                            </div>
                        `);
                        enableSubmitButton();
                        loadHistoryList(); // Atualiza status na lista lateral
                    }
                    
                    currentEventSource.close();
                    currentEventSource = null;
                }
            } catch (err) {
                console.error("Erro ao interpretar dados de streaming:", err);
            }
        };
        
        currentEventSource.onerror = function() {
            if (currentEventSource) {
                currentEventSource.close();
                currentEventSource = null;
            }
            appendTerminalLog("Conexão streaming finalizada.", "system");
            enableSubmitButton();
        };
    }

    // --- AUXILIARES DE UI ---

    function resetUIForNewRun() {
        // Limpar terminal
        $("#terminal-body").empty();
        // Limpar output
        $("#output-content").html(`
            <div class="empty-state">
                <i class="fa-solid fa-envelope-open-text glow-icon-large"></i>
                <h3>Processando dúvida...</h3>
                <p>Nossos agentes de IA estão analisando a dúvida, consultando os manuais e redigindo a resposta.</p>
            </div>
        `);
        // Reset status badge
        $("#job-status-badge").text("Ocioso").removeClass().addClass("status-badge");
        // Ocultar ações de HITL
        $("#hitl-actions-container").addClass("hidden");
        $("#human-feedback").val("");
        
        // Reset pipeline steps
        $(".pipeline-step").removeClass("active completed");
    }

    function enableSubmitButton() {
        $("#btn-submit").prop("disabled", false).find("span").text("Iniciar Atendimento");
        $("#btn-submit").find("i").removeClass("fa-spinner fa-spin").addClass("fa-circle-play");
    }

    function appendTerminalLog(message, sender = "system") {
        const timestamp = new Date().toLocaleTimeString();
        let logLine = "";
        
        if (sender === "system") {
            logLine = `<div class="log-line"><span class="timestamp">[${timestamp}]</span> <span style="color:#00f0ff">&gt; ${message}</span></div>`;
        } else {
            logLine = `<div class="log-line"><span class="timestamp">[${timestamp}]</span> <span class="agent">&gt; [Agente]:</span> ${message}</div>`;
        }
        
        const $body = $("#terminal-body");
        $body.append(logLine);
        $body.scrollTop($body[0].scrollHeight);
    }

    function updateTerminalLogs(logs) {
        if (!logs || logs.length === 0) return;
        
        // Escreve apenas novas linhas de log
        if (logs.length > loggedLinesCount) {
            for (let i = loggedLinesCount; i < logs.length; i++) {
                const line = logs[i];
                if (line.includes("Pensamento:") || line.includes("Ferramenta:") || line.includes("Iniciando") || line.includes("Buscando")) {
                    appendTerminalLog(line, "agent");
                } else {
                    appendTerminalLog(line, "system");
                }
            }
            loggedLinesCount = logs.length;
        }
    }

    function updateUIStatus(status) {
        const $badge = $("#job-status-badge");
        $badge.removeClass("working waiting done");
        
        switch (status) {
            case "triando":
                $badge.text("Triando (Haiku)").addClass("status-badge working");
                break;
            case "resolvendo":
                $badge.text("Resolvendo (Sonnet)").addClass("status-badge working");
                break;
            case "auditando":
                $badge.text("Auditando (Opus)").addClass("status-badge working");
                break;
            case "aguardando_aprovacao":
                $badge.text("Aprovação Pendente").addClass("status-badge waiting");
                break;
            case "concluido":
                $badge.text("Concluído").addClass("status-badge done");
                break;
            case "erro":
                $badge.text("Falhou").addClass("status-badge");
                break;
        }
    }

    function updatePipelineStep(stepId, state) {
        const $step = $("#" + stepId);
        if (state === "active") {
            $step.removeClass("completed").addClass("active");
        } else if (state === "completed") {
            $step.removeClass("active").addClass("completed");
        }
    }

    function managePipelineVisuals(status) {
        // Limpa estados temporários
        $(".pipeline-step").removeClass("active");
        
        if (status === "triando") {
            updatePipelineStep("step-cache", "completed");
            updatePipelineStep("step-triando", "active");
        } else if (status === "resolvendo") {
            updatePipelineStep("step-cache", "completed");
            updatePipelineStep("step-triando", "completed");
            updatePipelineStep("step-resolvendo", "active");
        } else if (status === "auditando") {
            updatePipelineStep("step-cache", "completed");
            updatePipelineStep("step-triando", "completed");
            updatePipelineStep("step-resolvendo", "completed");
            updatePipelineStep("step-auditando", "active");
        } else if (status === "aguardando_aprovacao") {
            updatePipelineStep("step-cache", "completed");
            updatePipelineStep("step-triando", "completed");
            updatePipelineStep("step-resolvendo", "completed");
            updatePipelineStep("step-auditando", "completed");
            updatePipelineStep("step-hitl", "active");
        } else if (status === "concluido") {
            updatePipelineStep("step-cache", "completed");
            updatePipelineStep("step-triando", "completed");
            updatePipelineStep("step-resolvendo", "completed");
            updatePipelineStep("step-auditando", "completed");
            updatePipelineStep("step-hitl", "completed");
        }
    }

    // --- EXIBIR RASCUNHO PARA HITL ---
    function showDraftForReview(draftMarkdown) {
        const htmlContent = parseMarkdown(draftMarkdown);
        $("#output-content").html(htmlContent);
        
        // Exibir ações do HITL
        $("#hitl-actions-container").removeClass("hidden");
        appendTerminalLog("💡 SISTEMA: Por favor, revise a resposta recomendada na tela.", "system");
    }

    // --- EXIBIR RESPOSTA CONCLUÍDA ---
    function showFinalResponse(finalMarkdown, cacheHit = false) {
        const htmlContent = parseMarkdown(finalMarkdown);
        $("#output-content").html(htmlContent);
        
        // Ocultar ações do HITL
        $("#hitl-actions-container").addClass("hidden");
        
        if (cacheHit) {
            appendTerminalLog("⚡ Resposta resgatada do cache semântico instantaneamente!", "system");
        } else {
            appendTerminalLog("🎉 Resposta de suporte finalizada e enviada para o cliente com sucesso!", "system");
        }
    }

    // --- CONTROLES HITL: APROVAÇÃO ---
    $("#btn-approve").click(function() {
        if (!currentJobId) return;
        
        $(this).prop("disabled", true).text("Aprovando...");
        
        $.post(`/api/approve/${currentJobId}`, function() {
            appendTerminalLog("✅ Resposta aprovada! Registrando no banco de cache semântico...", "system");
            $("#btn-approve").prop("disabled", false).html('<i class="fa-solid fa-check-double"></i> <span>Aprovar e Salvar no Cache</span>');
            startSSEConnection(currentJobId);
        }).fail(function() {
            appendTerminalLog("❌ Erro ao registrar aprovação no servidor.", "system");
            $("#btn-approve").prop("disabled", false).html('<i class="fa-solid fa-check-double"></i> <span>Aprovar e Salvar no Cache</span>');
        });
    });

    // --- CONTROLES HITL: REJEIÇÃO / FEEDBACK ---
    $("#btn-reject").click(function() {
        const feedback = $("#human-feedback").val().trim();
        if (!feedback) {
            alert("Por favor, digite o feedback de ajuste antes de refinar!");
            return;
        }
        
        if (!currentJobId) return;

        $(this).prop("disabled", true).text("Refinando...");
        $("#btn-approve").prop("disabled", true);
        
        $.ajax({
            url: `/api/reject/${currentJobId}`,
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ feedback: feedback }),
            success: function() {
                appendTerminalLog("🔄 Roteando feedback do operador para refinamento com Claude Opus...", "system");
                $("#hitl-actions-container").addClass("hidden"); // Oculta enquanto refina
                $("#human-feedback").val(""); // Limpa campo
                $("#btn-reject").prop("disabled", false).html('<i class="fa-solid fa-arrows-rotate"></i> <span>Refinar com Feedback</span>');
                $("#btn-approve").prop("disabled", false);
                
                // Reinicia streaming
                startSSEConnection(currentJobId);
            },
            error: function() {
                appendTerminalLog("❌ Erro ao enviar feedback de refinamento.", "system");
                $("#btn-reject").prop("disabled", false).html('<i class="fa-solid fa-arrows-rotate"></i> <span>Refinar com Feedback</span>');
                $("#btn-approve").prop("disabled", false);
            }
        });
    });

    // --- GERENCIAMENTO DE CACHE: CARREGAR TABELA ---
    function loadCacheTable() {
        $.get("/api/cache", function(cacheList) {
            const $tbody = $("#cache-list-body");
            $tbody.empty();
            
            if (!cacheList || cacheList.length === 0) {
                $tbody.append(`
                    <tr>
                        <td colspan="3" class="table-empty">Nenhum registro no cache semântico ainda.</td>
                    </tr>
                `);
                return;
            }
            
            cacheList.forEach(function(item, index) {
                // Cortar textos longos para não quebrar a tabela
                const shortQuery = item.query.length > 70 ? item.query.substring(0, 70) + "..." : item.query;
                const shortResponse = item.response.length > 80 ? item.response.substring(0, 80) + "..." : item.response;
                
                $tbody.append(`
                    <tr data-index="${index}">
                        <td><strong style="color: #c9d1d9">${shortQuery}</strong></td>
                        <td style="font-family: monospace; font-size: 11px;">${escapeHtml(shortResponse)}</td>
                        <td style="text-align: center">
                            <button class="btn-delete-cache" data-index="${index}">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        </td>
                    </tr>
                `);
            });

            // Bind de deleção
            $(".btn-delete-cache").click(function() {
                const idx = $(this).data("index");
                if (confirm("Tem certeza que deseja apagar essa resposta do cache semântico?")) {
                    $.ajax({
                        url: `/api/cache/${idx}`,
                        type: "DELETE",
                        success: function() {
                            appendTerminalLog(`💾 Registro de cache #${idx} removido com sucesso.`, "system");
                            loadCacheTable();
                        }
                    });
                }
            });
        });
    }

    $("#btn-refresh-cache").click(function() {
        loadCacheTable();
        appendTerminalLog("🔄 Tabela de cache semântico atualizada.", "system");
    });

    // --- RENDERIZADOR RÁPIDO DE MARKDOWN (REGEX-BASED) ---
    function parseMarkdown(text) {
        if (!text) return "";
        let html = text
            // Escapar tags HTML nativas por segurança contra XSS, exceto as criadas pelo parser
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            // Blocos de código pre-formatados com linguagem
            .replace(/```python\s*([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
            .replace(/```markdown\s*([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
            .replace(/```\s*([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
            // Código inline
            .replace(/`([^`]+)`/g, "<code>$1</code>")
            // Títulos H3, H2, H1
            .replace(/^### (.*$)/gim, "<h3>$1</h3>")
            .replace(/^## (.*$)/gim, "<h2>$1</h2>")
            .replace(/^# (.*$)/gim, "<h1>$1</h1>")
            // Listas ordenadas e não ordenadas
            .replace(/^\s*\-\s+(.*$)/gim, "<li>$1</li>")
            .replace(/^\s*\*\s+(.*$)/gim, "<li>$1</li>")
            // Negritos
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            // Itálicos
            .replace(/\*([^*]+)\*/g, "<em>$1</em>");

        // Tratamento de parágrafos simples e quebras de linha
        let paragraphs = html.split(/\n\n+/);
        html = paragraphs.map(p => {
            let trimmed = p.trim();
            if (!trimmed) return "";
            if (trimmed.startsWith('<pre>') || trimmed.startsWith('<h') || trimmed.startsWith('<li>')) {
                // Se já for cabeçalho, bloco de código ou lista, mantém
                return trimmed;
            }
            return `<p>${trimmed.replace(/\n/g, "<br>")}</p>`;
        }).join("");

        // Envolve blocos <li> soltos em <ul>
        html = html.replace(/(<li>.*<\/li>)/g, "<ul>$1</ul>");
        
        return html;
    }

    // Helper para escapar HTML simples
    function escapeHtml(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
