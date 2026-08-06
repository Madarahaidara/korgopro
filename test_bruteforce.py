import sys
sys.path.insert(0, '.')

from core.bruteforce_protection import BruteForceProtection

# Premier test
bfp = BruteForceProtection()
bfp.record_failed_attempt('test_user')
bfp.record_failed_attempt('test_user')
bfp.record_failed_attempt('test_user')
bfp.record_failed_attempt('test_user')
bfp.record_failed_attempt('test_user')
locked_after_5 = bfp.is_locked_out('test_user')
print(f'Apres 5 tentatives - locked: {locked_after_5}')

# Nouvelle instanciation (meme singleton)
bfp2 = BruteForceProtection()
locked_after_reinit = bfp2.is_locked_out('test_user')
print(f'Apres re-instanciation - locked: {locked_after_reinit}')
print(f'Memoire instances: {bfp is bfp2}')

# Vérifier si l'__init__ réinitialise l'état
print(f'failed_attempts contenu: {dict(bfp.failed_attempts)}')
print(f'lockout_durations contenu: {dict(bfp.lockout_durations)}')