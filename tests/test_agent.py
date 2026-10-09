from machia import LocalLlamaServer
from machia.tools import ToolRegistry, FINISH
from machia.agent import Agent
from machia.safety.policy import Policy
from machia.safety.audit import AuditLog
from machia.tools.system import SYS_INFO
from machia.tools.fs import FS_LIST
from machia.tools import ToolRegistry, FINISH, SYS_INFO, FS_LIST, FS_READ, FS_WRITE


def main():
    # 1. Build the tool registry.
    reg = ToolRegistry()
    reg.register(SYS_INFO)
    reg.register(FS_LIST)
    reg.register(FS_WRITE)
    reg.register(FINISH)

    # 2. Build the backend.
    backend = LocalLlamaServer()

    # 3. Build the agent.
    agent = Agent(
        backend=backend,
        registry=reg,
        workspace_root=r"C:\dev\machia-workspace",
        max_steps=8,
         policy=Policy(mode="confirm"),     # nothing changes yet: fs_list is low-risk
        audit=AuditLog(),
    )

    # 4. Give it a real task.
    task = "Create a file called notes.txt in my workspace with the text 'Hello from Machia'."
    print(f"TASK: {task}\n")
    answer = agent.run(task, verbose=True)
    print(f"\nFINAL ANSWER: {answer}")


if __name__ == "__main__":
    main()