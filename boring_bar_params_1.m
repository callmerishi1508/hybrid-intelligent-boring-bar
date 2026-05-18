clear; clc;

%% Modal parameters
fn   = [174,    614,    1130  ];
z    = [0.0120, 0.0063, 0.0018];
wn   = 2*pi*fn;
kxF  = [4.38e6,  -4.50e8, -1.24e8];
kxI  = [-4.38e5, -1.02e8, -1.90e8];
kxtF = [1.62e6,   1.72e7,  2.10e7];

den1 = [1, 2*z(1)*wn(1), wn(1)^2];
den2 = [1, 2*z(2)*wn(2), wn(2)^2];
den3 = [1, 2*z(3)*wn(3), wn(3)^2];

%% Unscaled plant TFs
GxI_13   = tf(wn(1)^2/kxI(1),den1) + tf(wn(3)^2/kxI(3),den3);
GxI_full = tf(wn(1)^2/kxI(1),den1) + tf(wn(2)^2/kxI(2),den2) + tf(wn(3)^2/kxI(3),den3);
GxFc_13  = tf(wn(1)^2/kxF(1),den1) + tf(wn(3)^2/kxF(3),den3);
GxtFc    = tf(wn(1)^2/kxtF(1),den1) + tf(wn(2)^2/kxtF(2),den2) + tf(wn(3)^2/kxtF(3),den3);

%% Paper weighting functions
Kp_WI=10;  f1_WI=500;  f2_WI=2000;
WI_paper = Kp_WI * tf([1/(2*pi*f1_WI),1],[1/(2*pi*f2_WI),1]);

Kp_Wx=3.2e6;  f1_Wx=165;  f2_Wx=535;
Wx_paper = Kp_Wx * tf([1/(2*pi*f1_Wx)^2,1/(2*pi*f1_Wx),1], [1/(2*pi*f2_Wx)^2,1/(2*pi*f2_Wx),1]);

%% Build generalized plant
G_ss = ss([GxFc_13, GxI_13]);   
G_ss.D(1,1) = 1e-8; % Regularization
G_ss.InputName  = {'Fc','I'};
G_ss.OutputName = {'x'};

WI_s = ss(WI_paper);
WI_s.InputName  = {'I'};
WI_s.OutputName = {'zI'};

Wx_s = ss(Wx_paper);
Wx_s.InputName  = {'x'};
Wx_s.OutputName = {'zx'};

Gp = connect(G_ss, WI_s, Wx_s, {'Fc','I'}, {'zI','zx','x'});
Gp = balreal(Gp);

if ~exist('output','dir')
    mkdir('output');
end

%% Synthesise
opt = hinfsynOptions('Display','off','Method','ric');
[K_raw, ~, gamma] = hinfsyn(Gp, 1, 1, opt); 
fprintf('\n--- SYNTHESIS COMPLETE ---\n');
fprintf('Optimal gamma: %.4f\n', gamma);

%% Notch sweep vs full plant
wn_n = 2*pi*614;
best_mrp = inf;  best_K = [];  best_params = [0,0];

for zz = [0.1, 0.05, 0.02, 0.01, 0.005]
    for zp = [0.3, 0.4, 0.5, 0.6, 0.7]
        Nt  = tf([1,2*zz*wn_n,wn_n^2],[1,2*zp*wn_n,wn_n^2]);
        Kt  = ss(K_raw * ss(Nt));
        
        % MUST evaluate stability using positive feedback (+1)
        CLt = feedback(GxI_13 * Kt, 1, +1); 
        
        mrp = max(real(pole(CLt)));
        if mrp < best_mrp
            best_mrp = mrp; best_K = Kt; best_params = [zz, zp];
        end
    end
end

if best_mrp < 0
    K_final = best_K;
    fprintf('\nBest notch filter: zz=%.3f, zp=%.1f\n', best_params(1), best_params(2));
else
    error('Could not stabilize with notch filter.');
end

%% Dynamic stiffness — analytical
kxtI = [-1.74e5, 1.05e6, 3.99e7]; 
freq_hz = logspace(log10(30), log10(3000), 500);
freq_w  = 2*pi*freq_hz;

[mag_OL,~] = bode(GxtFc, freq_w);
DS_OL = 1./squeeze(mag_OL)*1e-6;

% MUST use positive feedback (+1) for the tool tip calculations
GxtI_full = tf(wn(1)^2/kxtI(1), den1) + tf(wn(2)^2/kxtI(2), den2) + tf(wn(3)^2/kxtI(3), den3);
K_closed = feedback(K_final, GxI_13,+1); 
T_xtFc = GxtFc + GxtI_full * K_closed * GxFc_13;

[mag_CL,~] = bode(T_xtFc, freq_w);
DS_CL = 1./squeeze(mag_CL)*1e-6;

figure('Name','Dynamic stiffness — analytical');
semilogx(freq_hz, DS_OL,'b--','LineWidth',1.5,'DisplayName','Open loop'); hold on;
semilogx(freq_hz, DS_CL,'r','LineWidth',1.5,'DisplayName','H\infty CL');
xline([174,614,1130],'--k');
xlabel('Frequency (Hz)'); ylabel('Dynamic stiffness (N/µm)');
title('Boring bar — analytical closed loop'); legend; grid on;
xlim([30,3000]); ylim([0,0.6]);

%% Extract Simulink Matrices
fprintf('\n=== Dynamic stiffness ===\n');
targets = [0.381, 0.256, 0.159];
for i = 1:3
    w = 2*pi*fn(i);
    [m_ol, ~, ~] = bode(GxtFc,  w);
    [m_cl, ~, ~] = bode(T_xtFc, w);
    fprintf('Mode %d Hz -> Open Loop: %.4f | Closed Loop: %.4f | Target: %.4f\n', ...
            fn(i), 1/squeeze(m_ol)*1e-6, 1/squeeze(m_cl)*1e-6, targets(i));
end

[AK,BK,CK,DK] = ssdata(K_final);
fprintf('\nReady for Simulink State-Space block.\n');

%% Save H-inf design results
results.gamma = gamma;
results.best_params = best_params;
results.freq_hz = freq_hz;
results.DS_OL = DS_OL;
results.DS_CL = DS_CL;
results.K_matrices = struct('A', AK, 'B', BK, 'C', CK, 'D', DK);
save('output/hinf_results.mat', '-struct', 'results');

T = table(freq_hz', DS_OL, DS_CL, 'VariableNames', {'frequency_hz','DS_OL','DS_CL'});
writetable(T, 'output/hinf_dynamic_stiffness.csv');

sim_success = false;
fprintf('\nRunning Simulink model...\n');
try
    % Prefer the downgraded model if present
    if exist('boring_bar_R2025b.slx','file')
        model_to_sim = 'boring_bar_R2025b';
    else
        model_to_sim = 'boring_bar';
    end
    out = sim(model_to_sim);
    fprintf('Simulation complete. Loading data...\n');
    sim_success = true;
catch ME
    errFile = fopen('output/hinf_sim_error.txt', 'w');
    fprintf(errFile, 'Simulink simulation failed: %s\n', ME.message);
    fprintf(errFile, 'Stack trace:\n');
    for k = 1:numel(ME.stack)
        fprintf(errFile, '  %s (line %d)\n', ME.stack(k).file, ME.stack(k).line);
    end
    fclose(errFile);
    fprintf('Simulation failed: %s\n', ME.message);
end

if sim_success
    t = out.tout;
    xt = out.xt_sim;
    Fc = out.Fc_sim;    % need this — add To Workspace on Fc line

    %% Basic checks
    Fs = 1/mean(diff(t));
    fprintf('Sample rate: %.0f Hz\n', Fs);
    fprintf('Duration: %.3f s\n', t(end));
    fprintf('Samples: %d\n', length(t));

        %% Export minimal CSV for CNN inference
        try
            Tcsv = table(t, xt, Fc, 'VariableNames', {'timestamp','x_sensor','u_hinf'});
            writetable(Tcsv, 'simscape_export.csv');
            writetable(Tcsv, fullfile('output','simscape_export.csv'));
            fprintf('Exported simscape_export.csv\n');
        catch CSV_E
            fprintf('Failed to write simscape_export.csv: %s\n', CSV_E.message);
        end

    %% Compute FRF using Welch method (guard for missing Signal Processing Toolbox)
    N_fft = 2048;
    Txy = [];
    f = [];
    try
        if exist('tfestimate','file') == 2
            if exist('hann','file') == 2
                win = hann(N_fft);
            else
                n = (0:N_fft-1)';
                win = 0.5 * (1 - cos(2*pi*n/(N_fft-1))); % fallback Hann
            end
            [Txy, f] = tfestimate(Fc, xt, win, N_fft/2, N_fft, Fs);
        else
            warning('tfestimate not available. Skipping FRF estimation.');
        end
    catch FRF_E
        warning('FRF estimation failed: %s', FRF_E.message);
    end

    if ~isempty(Txy)
        %% Dynamic stiffness = 1/|FRF|  in N/µm
        DS_CL_sim = 1 ./ abs(Txy) * 1e-6;

        save('output/hinf_sim_data.mat', 't', 'xt', 'Fc', 'f', 'DS_CL_sim');
        T_sim = table(f, DS_CL_sim, 'VariableNames', {'frequency_hz','DS_CL_sim'});
        writetable(T_sim, 'output/hinf_sim_dynamic_stiffness.csv');
    else
        save('output/hinf_sim_data.mat', 't', 'xt', 'Fc');
        warning('Skipping dynamic stiffness CSV/plot due to missing FRF data.');
    end
end

if sim_success

    %% Open loop analytical reference and plotting (only if FRF available)
    if exist('f','var') && ~isempty(f) && exist('DS_CL_sim','var')
        fn   = [174,    614,    1130  ];
        z    = [0.0120, 0.0063, 0.0018];
        wn   = 2*pi*fn;
        kxtF = [1.62e6, 1.72e7, 2.10e7];
        den1 = [1, 2*z(1)*wn(1), wn(1)^2];
        den2 = [1, 2*z(2)*wn(2), wn(2)^2];
        den3 = [1, 2*z(3)*wn(3), wn(3)^2];

        GxtFc = tf(wn(1)^2/kxtF(1),den1) + ...
            tf(wn(2)^2/kxtF(2),den2) + ...
            tf(wn(3)^2/kxtF(3),den3);

        [mag_OL,~] = bode(GxtFc, 2*pi*f);
        DS_OL = 1./squeeze(mag_OL)*1e-6;

        %% Plot
        figure('Name','Dynamic Stiffness — Simscape Result');
        semilogx(f, DS_OL,    'b--', 'LineWidth',1.5, 'DisplayName','Open loop'); hold on;
        semilogx(f, DS_CL_sim,'r',   'LineWidth',1.5, 'DisplayName','H\infty closed loop (Simscape)');
        xline(174,  '--k', '174 Hz',  'LabelVerticalAlignment','bottom');
        xline(614,  '--k', '614 Hz',  'LabelVerticalAlignment','bottom');
        xline(1130, '--k', '1130 Hz', 'LabelVerticalAlignment','bottom');
        xlabel('Frequency (Hz)');
        ylabel('Dynamic stiffness (N/\\mum)');
        title('Boring bar — Simscape H\infty closed-loop result');
        legend('Location','northwest');
        grid on;
        xlim([30 3000]);
        ylim([0 0.6]);

        %% Print values at modal frequencies
        fprintf('\n=== Dynamic stiffness at modal frequencies ===\n');
        fprintf('%-10s %-15s %-15s %-12s\n','Mode Hz','Simscape CL','Open loop','Paper target');
        targets = [0.381, 0.256, 0.159];
        for i = 1:3
            [~, idx] = min(abs(f - fn(i)));
            [m_ol,~] = bode(GxtFc, 2*pi*fn(i));
            fprintf('%-10d %-15.4f %-15.4f %-12.4f\n', ...
                fn(i), DS_CL_sim(idx), 1/squeeze(m_ol)*1e-6, targets(i));
        end
    else
        warning('Skipping Simscape FRF plot and modal dynamic-stiffness table due to missing FRF results.');
    end

    %% Control current check
    I_data = out.I_sim;
    fprintf('\nPeak control current: %.4f A\n', max(abs(I_data)));
    if max(abs(I_data)) > 4.0
        fprintf('WARNING: exceeds 4A amplifier limit\n');
    else
        fprintf('Within amplifier limit\n');
    end
end
