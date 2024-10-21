from time import sleep

from django.core.management.base import BaseCommand

from agent.models import RetellGIAgentCall, RetellZepboundAgentCall


class Command(BaseCommand):
    help = "Generate a summary of calls from the last 24 hours"

    def handle(self, *args, **kwargs):
        RetellGIAgentCall.generate_report()
        sleep(5)
        RetellZepboundAgentCall.generate_report()
        return
