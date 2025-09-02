from django.core.management.base import BaseCommand
import subprocess
import sys
import os
from pathlib import Path


class Command(BaseCommand):
    help = 'Start Celery workers with proper queue configuration for post-payment processing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--workers',
            type=int,
            default=4,
            help='Number of worker processes to start (default: 4)'
        )
        parser.add_argument(
            '--loglevel',
            type=str,
            default='info',
            choices=['debug', 'info', 'warning', 'error', 'critical'],
            help='Logging level (default: info)'
        )
        parser.add_argument(
            '--queues',
            type=str,
            default='default,post_payment,emails,pos_sync,analytics,loyalty,inventory',
            help='Comma-separated list of queues to process (default: all queues)'
        )
        parser.add_argument(
            '--beat',
            action='store_true',
            help='Also start Celery beat scheduler'
        )
        parser.add_argument(
            '--flower',
            action='store_true',
            help='Also start Flower monitoring tool'
        )

    def handle(self, *args, **options):
        workers = options['workers']
        loglevel = options['loglevel']
        queues = options['queues']
        start_beat = options['beat']
        start_flower = options['flower']

        # Ensure logs directory exists
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)

        self.stdout.write(
            self.style.SUCCESS(
                f'Starting Celery workers with {workers} processes...'
            )
        )
        self.stdout.write(f'Queues: {queues}')
        self.stdout.write(f'Log level: {loglevel}')

        # Base celery worker command
        worker_cmd = [
            sys.executable, '-m', 'celery',
            '-A', 'rms_backend',
            'worker',
            '--loglevel', loglevel,
            '--concurrency', str(workers),
            '--queues', queues,
            '--logfile', 'logs/celery_worker.log',
            '--pidfile', 'logs/celery_worker.pid',
        ]

        # Start worker
        try:
            self.stdout.write('Starting Celery worker...')
            worker_process = subprocess.Popen(
                worker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Start beat scheduler if requested
            beat_process = None
            if start_beat:
                self.stdout.write('Starting Celery beat scheduler...')
                beat_cmd = [
                    sys.executable, '-m', 'celery',
                    '-A', 'rms_backend',
                    'beat',
                    '--loglevel', loglevel,
                    '--logfile', 'logs/celery_beat.log',
                    '--pidfile', 'logs/celery_beat.pid',
                ]
                beat_process = subprocess.Popen(
                    beat_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )

            # Start Flower monitoring if requested
            flower_process = None
            if start_flower:
                self.stdout.write('Starting Flower monitoring on http://localhost:5555...')
                flower_cmd = [
                    sys.executable, '-m', 'celery',
                    '-A', 'rms_backend',
                    'flower',
                    '--port=5555',
                    '--logfile', 'logs/celery_flower.log',
                ]
                flower_process = subprocess.Popen(
                    flower_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )

            self.stdout.write(
                self.style.SUCCESS(
                    'Celery services started successfully!\n'
                    'Worker PID file: logs/celery_worker.pid\n'
                    'Worker log file: logs/celery_worker.log'
                )
            )
            
            if start_beat:
                self.stdout.write(
                    'Beat PID file: logs/celery_beat.pid\n'
                    'Beat log file: logs/celery_beat.log'
                )
            
            if start_flower:
                self.stdout.write(
                    'Flower monitoring: http://localhost:5555\n'
                    'Flower log file: logs/celery_flower.log'
                )

            self.stdout.write(
                self.style.WARNING(
                    '\nPress Ctrl+C to stop all services...'
                )
            )

            # Wait for processes
            try:
                worker_process.wait()
            except KeyboardInterrupt:
                self.stdout.write('\nShutting down Celery services...')
                worker_process.terminate()
                if beat_process:
                    beat_process.terminate()
                if flower_process:
                    flower_process.terminate()
                
                # Wait for graceful shutdown
                worker_process.wait(timeout=10)
                if beat_process:
                    beat_process.wait(timeout=5)
                if flower_process:
                    flower_process.wait(timeout=5)
                
                self.stdout.write(
                    self.style.SUCCESS('Celery services stopped successfully!')
                )

        except subprocess.CalledProcessError as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to start Celery worker: {e}')
            )
            sys.exit(1)
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(
                    'Celery not found. Please install it with: pip install celery[redis]'
                )
            )
            sys.exit(1)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Unexpected error: {e}')
            )
            sys.exit(1)