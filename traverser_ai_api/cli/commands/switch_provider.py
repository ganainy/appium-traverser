"""
CLI command to switch AI provider at runtime.
"""
from traverser_ai_api.cli.commands.base import CommandHandler, CommandResult
from traverser_ai_api.cli.shared.context import CLIContext

class SwitchProviderCommand(CommandHandler):
    """Switch the AI provider and reload config at runtime."""
    @property
    def name(self):
        return "switch-provider"

    @property
    def description(self):
        return "Switch the AI provider (gemini, openrouter, ollama) and reload config live."

    def register(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help=self.description,
            description=self.description
        )
        parser.add_argument("provider", type=str, help="AI provider to use (gemini, openrouter, ollama)")
        parser.add_argument("--model", type=str, default=None, help="Model name/alias to use")
        return parser

    def run(self, args, context: CLIContext):
        provider = args.provider.strip().lower()
        if provider not in ("gemini", "openrouter", "ollama"):
            return CommandResult(
                success=False,
                message=f"[ERROR] Invalid provider: {provider}",
                exit_code=1
            )
        # Update config and save
        context.config.AI_PROVIDER = provider
        if args.model:
            context.config.DEFAULT_MODEL_TYPE = args.model
        context.config.save_user_config()
        # Optionally reload session/agent if needed (future extension)
        return CommandResult(
            success=True,
            message=f"Provider switched to '{provider}'. Please restart session/command if required.",
            exit_code=0
        )
