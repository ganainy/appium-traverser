
"""
CLI command to switch AI provider at runtime.
"""
from cli.commands.base import CommandHandler, CommandResult
from cli.shared.context import CLIContext
from cli.constants import messages as MSG
from cli.constants import keys as KEYS

class SwitchProviderCommand(CommandHandler):
    """Switch the AI provider and reload config at runtime."""
    @property
    def name(self):
        return MSG.SWITCH_PROVIDER_NAME

    @property
    def description(self):
        return MSG.SWITCH_PROVIDER_DESC.format(providers=", ".join(KEYS.VALID_AI_PROVIDERS))

    def register(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument(
            "provider",
            type=str,
            help=MSG.SWITCH_PROVIDER_ARG_HELP.format(providers=", ".join(KEYS.VALID_AI_PROVIDERS))
        )
        parser.add_argument(
            "--model",
            type=str,
            default=None,
            help=MSG.SWITCH_PROVIDER_MODEL_ARG_HELP
        )
        parser.set_defaults(handler=self)
        return parser

    def run(self, args, context: CLIContext):
        result = context.config.switch_ai_provider(args.provider.strip().lower(), args.model)
        # Optionally wrap result in CommandResult with user-facing message
        if getattr(result, 'success', True):
            return CommandResult(success=True, message=MSG.SWITCH_PROVIDER_SUCCESS.format(provider=args.provider))
        else:
            return CommandResult(success=False, message=MSG.SWITCH_PROVIDER_FAIL.format(provider=args.provider))
