"""Shared AWS access for the deployment tasks.

No credentials are ever read, logged or embedded here. The default runner refuses to
call anything, so live acceptance is explicitly BLOCKED until an authorized runner and
credentials are supplied; deterministic tests inject a fake runner.
"""


class AwsEnvironmentError(RuntimeError):
    """AWS CLI, credentials or an authorized envelope are unavailable."""


class AwsAuthError(RuntimeError):
    """AWS rejected the credentials; the caller must reauthenticate."""


class Aws:
    def __init__(self, runner=None, region=None):
        self.runner = runner
        self.region = region

    def call(self, *arguments):
        if self.runner is None:
            raise AwsEnvironmentError('AWS is not available on this host; live acceptance BLOCKED')
        command = [str(argument) for argument in arguments]
        if self.region and '--region' not in command:
            command += ['--region', self.region]
        try:
            result = self.runner(command)
        except AwsAuthError:
            raise
        except Exception as error:
            raise AwsEnvironmentError('AWS call failed: ' + type(error).__name__) from error
        if not isinstance(result, dict):
            raise AwsEnvironmentError('AWS runner returned an unexpected result')
        return result
