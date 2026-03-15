import { CheckCircle2, Award, Calendar, LogOut } from 'lucide-react';

interface CompletionProps {
    onRestart: () => void;
}

export default function InterviewCompletion({ onRestart }: CompletionProps) {
    return (
        <div className="h-screen w-full flex items-center justify-center p-4 bg-[var(--bg-primary)] overflow-hidden">
            {/* Background Glow */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-indigo-500/10 blur-[120px] rounded-full" />

            <div className="glass-card w-full max-w-lg p-10 text-center animate-fade-in shadow-2xl relative z-10 border-indigo-500/20">
                <div className="w-24 h-24 bg-emerald-500/10 rounded-full flex items-center justify-center mx-auto mb-8 border border-emerald-500/20 animate-bounce-subtle">
                    <CheckCircle2 className="w-12 h-12 text-emerald-500" />
                </div>

                <h1 className="text-3xl font-extrabold text-[var(--text-primary)] mb-4 tracking-tight">
                    Assessment Submitted!
                </h1>

                <p className="text-[var(--text-secondary)] text-sm mb-10 leading-relaxed max-w-sm mx-auto font-medium">
                    Your interview has been successfully recorded and processed by our AI Monitoring System. Our recruitment team will review your results shortly.
                </p>

                <div className="grid grid-cols-2 gap-4 mb-10">
                    <div className="p-4 rounded-2xl bg-white/5 border border-white/5 text-left">
                        <Award className="w-5 h-5 text-indigo-400 mb-2" />
                        <h4 className="text-[var(--text-primary)] text-xs font-bold">Status</h4>
                        <p className="text-[var(--text-secondary)] text-[10px] font-bold uppercase tracking-wider text-emerald-400">Successfully Logged</p>
                    </div>
                    <div className="p-4 rounded-2xl bg-white/5 border border-white/5 text-left">
                        <Calendar className="w-5 h-5 text-indigo-400 mb-2" />
                        <h4 className="text-[var(--text-primary)] text-xs font-bold">Date</h4>
                        <p className="text-[var(--text-secondary)] text-[10px] uppercase font-bold text-indigo-300">{new Date().toLocaleDateString()}</p>
                    </div>
                </div>

                <div className="flex flex-col gap-4">
                    <button
                        onClick={() => window.location.reload()}
                        className="w-full bg-slate-800/80 hover:bg-slate-700 text-white font-bold py-4 rounded-xl border border-white/5 transition-all active:scale-[0.98] flex items-center justify-center gap-2 text-sm"
                    >
                        <LogOut className="w-4 h-4" />
                        Log Out & Exit
                    </button>

                    <p className="text-[var(--text-secondary)] text-[9px] font-bold uppercase tracking-widest opacity-50">
                        Session ID Auto-Saved to Database
                    </p>
                </div>
            </div>
        </div>
    );
}
