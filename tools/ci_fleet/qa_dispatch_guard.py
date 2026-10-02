"""تمييز فحص يدوي فعلي على البصمة نفسها؛ لا يصدر حكم جودة أو ترقية."""
def has_current_manual_sample(report, sha):
    sample = report.get('sample') or {}
    return (report.get('sha256') == sha and report.get('source') == 'ci'
            and sample.get('seedSalt') in ('rs1', 'rs2', 'rs3', 'rs4')
            and bool(sample.get('rows')))
