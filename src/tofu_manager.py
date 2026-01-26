import subprocess
import os
import json
import shutil
from pathlib import Path

class TofuManager:
    def __init__(self, template_dir: str, work_dir: str):
        """
        :param template_dir: Path to the directory containing main.tf (source)
        :param work_dir: Path where tofu init/apply will run (instance specific)
        """
        self.template_dir = Path(template_dir).resolve()
        self.work_dir = Path(work_dir).resolve()

    def _run_command(self, args, env=None):
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        
        # Ensure work dir exists
        self.work_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            ["tofu"] + args,
            cwd=str(self.work_dir),
            env=full_env,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise Exception(f"Tofu command failed: {args}\nStderr: {result.stderr}\nStdout: {result.stdout}")
        
        return result.stdout

    def init(self, env: dict = None, backend_config: dict = None):
        # If the work dir is empty, we might need to copy templates first
        # Ideally, we don't modify the template dir. 
        # Standard pattern: copy source files to work_dir.
        
        # Clean sync of tf files
        self.work_dir.mkdir(parents=True, exist_ok=True)
        for file in self.template_dir.glob("*.tf"):
            shutil.copy(file, self.work_dir)
            
        args = ["init", "-no-color"]
        if backend_config:
            for k, v in backend_config.items():
                args.append(f"-backend-config={k}={v}")

        return self._run_command(args, env=env)

    def apply(self, vars_dict: dict, env: dict = None):
        # Construct -var arguments
        args = ["apply", "-auto-approve", "-no-color", "-input=false"]
        for k, v in vars_dict.items():
            # For complex types (maps), we might need json encoding, keeping it simple for now
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            args.extend(["-var", f"{k}={v}"])
            
        return self._run_command(args, env=env)

    def destroy(self, vars_dict: dict, env: dict = None):
        args = ["destroy", "-auto-approve", "-no-color", "-input=false"]
        for k, v in vars_dict.items():
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            args.extend(["-var", f"{k}={v}"])
            
        return self._run_command(args, env=env)

    def plan(self, vars_dict: dict, env: dict = None, detailed_exitcode: bool = True):
        """
        Runs tofu plan.
        If detailed_exitcode is True:
          - Exit code 0: Succeeded, diff is empty (no changes detected)
          - Exit code 1: Error
          - Exit code 2: Succeeded, there is a diff
        """
        args = ["plan", "-no-color", "-input=false"]
        if detailed_exitcode:
            args.append("-detailed-exitcode")
            
        for k, v in vars_dict.items():
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            args.extend(["-var", f"{k}={v}"])
            
        # We need to handle exit codes manually for plan
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        result = subprocess.run(
            ["tofu"] + args,
            cwd=str(self.work_dir),
            env=full_env,
            capture_output=True,
            text=True
        )
        
        return result.returncode, result.stdout

    def output(self):
        stdout = self._run_command(["output", "-json", "-no-color"])
        return json.loads(stdout)
