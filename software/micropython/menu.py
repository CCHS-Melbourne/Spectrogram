import asyncio
from asyncio import Queue

class Menu:
    def __init__(self, options):
        """
        Initialize the menu with a list of options.
        
        :param options: List of menu options
        """
        self.options = options
        self.current_selection = 0
        self.queue = Queue()

    async def start(self):
        """
        Start the menu interaction.
        """
        display_task = asyncio.create_task(self.display())
        input_task = asyncio.create_task(self.handle_input())

        await asyncio.gather(display_task, input_task)

    async def display(self):
        """
        Display the menu options.
        """
        while True:
            for index, option in enumerate(self.options):
                prefix = "-> " if index == self.current_selection else "   "
                print(f"{prefix}{option}")
            await asyncio.sleep(1)

    async def handle_input(self):
        """
        Handle user input.
        """
        while True:
            user_input = await self.queue.get()
            if user_input == 'n':
                self.next_option()
            elif user_input == 'p':
                self.previous_option()
            elif user_input == 's':
                selected_option = self.select_option()
                print(f"Selected option: {selected_option}")
                break
            else:
                print("Invalid input, please try again.")

    def next_option(self):
        """
        Move to the next menu option.
        """
        self.current_selection = (self.current_selection + 1) % len(self.options)

    def previous_option(self):
        """
        Move to the previous menu option.
        """
        self.current_selection = (self.current_selection - 1) % len(self.options)

    def select_option(self):
        """
        Select the current menu option.
        
        :return: The selected option
        """
        return self.options[self.current_selection]

    async def add_input(self, user_input):
        """
        Add user input to the queue.
        
        :param user_input: The user input
        """
        await self.queue.put(user_input)