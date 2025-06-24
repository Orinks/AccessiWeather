import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

class AccessiWeather(toga.App):

    def startup(self):
        main_box = toga.Box(style=Pack(direction=COLUMN))

        name_label = toga.Label(
            'Hello, Toga!',
            style=Pack(padding=(0, 5))
        )

        main_box.add(name_label)

        # Create a menu bar
        file_menu = toga.Group('File')
        help_menu = toga.Group('Help')

        def save_handler(widget):
            print("Save menu item clicked")

        def about_handler(widget):
            self.main_window.info_dialog('AccessiWeather', 'An accessible weather application.')

        save_command = toga.Command(save_handler, 'Save', group=file_menu)
        exit_command = toga.Command(lambda _: self.exit(), 'Exit', group=file_menu)
        about_command = toga.Command(about_handler, 'About', group=help_menu)

        self.commands.add(save_command, exit_command, about_command)

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

def main():
    return AccessiWeather('AccessiWeather', 'net.orinks.accessiweather')
