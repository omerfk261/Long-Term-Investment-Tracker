import sys
import time
import uuid
import json
import os
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QDateEdit, QTabWidget, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, QDate, Qt
from tradingview_ta import TA_Handler, Interval
from plyer import notification

DATA_FILE = "portfolio.json"

class WorkerThread(QThread):
    update_signal = pyqtSignal(str, int, float, float, float, float)
    alert_signal = pyqtSignal(str, float, float)

    def __init__(self):
        super().__init__()
        self.portfolio = {} 
        self.running = True

    def run(self):
        while self.running:
            if self.portfolio:
                try:
                    usd_handler = TA_Handler(symbol="USDTRY", exchange="FX_IDC", screener="forex", interval=Interval.INTERVAL_1_MINUTE)
                    usd_try_rate = float(usd_handler.get_analysis().indicators["close"])

                    for pid, item in list(self.portfolio.items()):
                        try:
                            bist_handler = TA_Handler(symbol=item["symbol"], exchange="BIST", screener="turkey", interval=Interval.INTERVAL_1_MINUTE)
                            current_tl = float(bist_handler.get_analysis().indicators["close"])
                            current_usd = current_tl / usd_try_rate
                            
                            entry_date = datetime.strptime(item["date"], "%Y-%m-%d")
                            days_held = (datetime.now() - entry_date).days
                            display_days = days_held if days_held >= 0 else 0
                            math_days = days_held if days_held > 0 else 1 
                            
                            current_total = current_usd * item["lot"]
                            profit_pct_decimal = (current_usd - item["entry_usd"]) / item["entry_usd"]
                            simple_return = profit_pct_decimal * 100
                            apr = simple_return * (365 / math_days)
                            
                            self.update_signal.emit(pid, display_days, current_usd, current_total, simple_return, apr)

                            if current_usd >= item["target"]:
                                self.alert_signal.emit(item["symbol"], current_usd, item["target"])
                                
                        except Exception as e:
                            continue
                            
                except Exception as e:
                    print(f"Genel veri çekme hatası: {e}")
            
            time.sleep(60)

class BorsaTerminali(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Uzun Vadeli Portföy & Hedef Takibi")
        self.resize(1150, 500)

        self.history = [] # Geçmiş işlemleri tutacağımız liste

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Sekme (Tab) Sistemi Kurulumu
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_active = QWidget()
        self.tab_history = QWidget()
        self.tabs.addTab(self.tab_active, "Aktif Pozisyonlar")
        self.tabs.addTab(self.tab_history, "Geçmiş İşlemler")

        self.setup_active_tab()
        self.setup_history_tab()

        self.worker = WorkerThread()
        self.worker.update_signal.connect(self.update_table)
        self.worker.alert_signal.connect(self.send_notification)
        
        self.load_portfolio()
        self.worker.start()

    def setup_active_tab(self):
        layout = QVBoxLayout(self.tab_active)
        input_layout = QHBoxLayout()
        
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        
        self.symbol_input = QLineEdit()
        self.symbol_input.setPlaceholderText("Hisse (Örn: THYAO)")
        
        self.lot_input = QLineEdit()
        self.lot_input.setPlaceholderText("Lot Adedi")
        
        self.entry_input = QLineEdit()
        self.entry_input.setPlaceholderText("Giriş (USD)")

        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("Hedef (USD)")
        
        self.add_btn = QPushButton("Ekle")
        self.add_btn.clicked.connect(self.add_to_portfolio)

        input_layout.addWidget(self.date_input)
        input_layout.addWidget(self.symbol_input)
        input_layout.addWidget(self.lot_input)
        input_layout.addWidget(self.entry_input)
        input_layout.addWidget(self.target_input)
        input_layout.addWidget(self.add_btn)
        layout.addLayout(input_layout)

        self.active_table = QTableWidget(0, 12)
        self.active_table.setHorizontalHeaderLabels([
            "Tarih", "Gün", "Hisse", "Lot", "Giriş ($)", "T. Yatırım ($)", 
            "Hedef ($)", "Anlık ($)", "Güncel Değer ($)", "Değişim (%)", "APR (%)", "İşlem"
        ])
        self.active_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.active_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.active_table.horizontalHeader().setSectionResizeMode(11, QHeaderView.ResizeMode.ResizeToContents)
        
        self.active_table.itemChanged.connect(self.on_item_changed)
        layout.addWidget(self.active_table)

    def setup_history_tab(self):
        layout = QVBoxLayout(self.tab_history)
        
        self.history_table = QTableWidget(0, 10)
        self.history_table.setHorizontalHeaderLabels([
            "Giriş Tarihi", "Kapanış Tarihi", "Hisse", "Lot", "Giriş ($)", 
            "Çıkış ($)", "T. Yatırım ($)", "T. Çıkış ($)", "Kâr/Zarar (%)", "APR (%)"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Tabloyu kilitliyoruz (Sadece okuma)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) 
        layout.addWidget(self.history_table)

    def create_table_item(self, text, editable=False):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def insert_row_to_active(self, pid, date_str, symbol, lot, entry_usd, target_usd):
        self.active_table.blockSignals(True)
        row_index = self.active_table.rowCount()
        self.active_table.insertRow(row_index)
        
        total_investment = lot * entry_usd
        
        date_item = self.create_table_item(date_str, editable=True)
        date_item.setData(Qt.ItemDataRole.UserRole, pid)
        self.active_table.setItem(row_index, 0, date_item)
        
        self.active_table.setItem(row_index, 1, self.create_table_item("...", editable=False))
        self.active_table.setItem(row_index, 2, self.create_table_item(symbol, editable=False))
        self.active_table.setItem(row_index, 3, self.create_table_item(lot, editable=True))
        self.active_table.setItem(row_index, 4, self.create_table_item(f"{entry_usd:.2f}", editable=True))
        self.active_table.setItem(row_index, 5, self.create_table_item(f"{total_investment:.2f}", editable=False))
        self.active_table.setItem(row_index, 6, self.create_table_item(f"{target_usd:.2f}", editable=True))
        self.active_table.setItem(row_index, 7, self.create_table_item("...", editable=False))
        self.active_table.setItem(row_index, 8, self.create_table_item("...", editable=False))
        self.active_table.setItem(row_index, 9, self.create_table_item("...", editable=False))
        self.active_table.setItem(row_index, 10, self.create_table_item("...", editable=False))
        
        # Butonlar için Yatay Düzen (Tick ve Çarpı)
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)
        
        btn_tick = QPushButton("✔️")
        btn_cross = QPushButton("❌")
        
        btn_tick.setToolTip("Pozisyonu Kapat ve Geçmişe Ekle")
        btn_cross.setToolTip("Kaydı Tamamen Sil")
        
        btn_tick.clicked.connect(lambda _, row_id=pid: self.close_position(row_id))
        btn_cross.clicked.connect(lambda _, row_id=pid: self.delete_row(row_id))
        
        action_layout.addWidget(btn_tick)
        action_layout.addWidget(btn_cross)
        
        self.active_table.setCellWidget(row_index, 11, action_widget)
        self.active_table.blockSignals(False)

    def insert_row_to_history(self, hist_data):
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)
        
        self.history_table.setItem(row, 0, self.create_table_item(hist_data.get("entry_date", "-")))
        self.history_table.setItem(row, 1, self.create_table_item(hist_data.get("close_date", "-")))
        self.history_table.setItem(row, 2, self.create_table_item(hist_data.get("symbol", "-")))
        self.history_table.setItem(row, 3, self.create_table_item(hist_data.get("lot", "-")))
        self.history_table.setItem(row, 4, self.create_table_item(hist_data.get("entry_usd", "-")))
        self.history_table.setItem(row, 5, self.create_table_item(hist_data.get("exit_usd", "-")))
        self.history_table.setItem(row, 6, self.create_table_item(hist_data.get("total_inv", "-")))
        self.history_table.setItem(row, 7, self.create_table_item(hist_data.get("total_exit", "-")))
        
        ret_item = self.create_table_item(hist_data.get("profit_pct", "-"))
        if "%" in ret_item.text() and not ret_item.text().startswith("-"):
            ret_item.setForeground(Qt.GlobalColor.green)
        elif ret_item.text().startswith("-"):
            ret_item.setForeground(Qt.GlobalColor.red)
        self.history_table.setItem(row, 8, ret_item)
        
        apr_item = self.create_table_item(hist_data.get("apr", "-"))
        if "%" in apr_item.text() and not apr_item.text().startswith("-"):
            apr_item.setForeground(Qt.GlobalColor.green)
        elif apr_item.text().startswith("-"):
            apr_item.setForeground(Qt.GlobalColor.red)
        self.history_table.setItem(row, 9, apr_item)

    def add_to_portfolio(self):
        symbol = self.symbol_input.text().upper().strip()
        date_str = self.date_input.date().toString("yyyy-MM-dd")
        
        try:
            lot = float(self.lot_input.text())
            entry_usd = float(self.entry_input.text())
            target_usd = float(self.target_input.text())
        except ValueError:
            print("Lütfen Lot, Giriş ve Hedef kısımlarına sayı girin.")
            return

        pid = str(uuid.uuid4())
        self.insert_row_to_active(pid, date_str, symbol, lot, entry_usd, target_usd)

        self.worker.portfolio[pid] = {
            "symbol": symbol,
            "lot": lot,
            "entry_usd": entry_usd,
            "target": target_usd,
            "date": date_str
        }

        self.symbol_input.clear()
        self.lot_input.clear()
        self.entry_input.clear()
        self.target_input.clear()
        self.save_portfolio()

    def close_position(self, pid):
        # Arka plandan son veriyi ve satırı bul
        row_to_close = -1
        for row in range(self.active_table.rowCount()):
            item = self.active_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == pid:
                row_to_close = row
                break
                
        if row_to_close == -1 or pid not in self.worker.portfolio:
            return

        # Henüz hesaplama bitmediyse işlemi reddet
        if self.active_table.item(row_to_close, 7).text() in ["...", "Hesaplanıyor..."]:
            QMessageBox.warning(self, "Uyarı", "Veriler henüz hesaplanmadı. Lütfen birkaç saniye bekleyin.")
            return

        p_data = self.worker.portfolio[pid]
        
        # Arayüzden anlık değerleri alıyoruz
        exit_usd = self.active_table.item(row_to_close, 7).text()
        total_inv = self.active_table.item(row_to_close, 5).text()
        total_exit = self.active_table.item(row_to_close, 8).text()
        profit_pct = self.active_table.item(row_to_close, 9).text()
        apr = self.active_table.item(row_to_close, 10).text()

        hist_record = {
            "entry_date": p_data["date"],
            "close_date": datetime.now().strftime("%Y-%m-%d"),
            "symbol": p_data["symbol"],
            "lot": str(p_data["lot"]),
            "entry_usd": f'{p_data["entry_usd"]:.2f}',
            "exit_usd": exit_usd,
            "total_inv": total_inv,
            "total_exit": total_exit,
            "profit_pct": profit_pct,
            "apr": apr
        }
        
        self.history.append(hist_record)
        self.insert_row_to_history(hist_record)
        self.delete_row(pid) # Aktif tablodan kaldır ve kaydet

    def on_item_changed(self, item):
        col = item.column()
        if col not in [0, 3, 4, 6]: 
            return

        row = item.row()
        tarih_item = self.active_table.item(row, 0)
        if not tarih_item: return
        
        pid = tarih_item.data(Qt.ItemDataRole.UserRole)
        if pid not in self.worker.portfolio:
            return

        new_value = item.text().strip()
        try:
            if col == 0:
                datetime.strptime(new_value, "%Y-%m-%d") 
                self.worker.portfolio[pid]["date"] = new_value
            elif col == 3:
                val = float(new_value)
                self.worker.portfolio[pid]["lot"] = val
                entry = self.worker.portfolio[pid]["entry_usd"]
                self.active_table.blockSignals(True)
                self.active_table.item(row, 5).setText(f"{val * entry:.2f}")
                self.active_table.blockSignals(False)
            elif col == 4:
                val = float(new_value)
                self.worker.portfolio[pid]["entry_usd"] = val
                lot = self.worker.portfolio[pid]["lot"]
                self.active_table.blockSignals(True)
                self.active_table.item(row, 5).setText(f"{lot * val:.2f}")
                self.active_table.blockSignals(False)
            elif col == 6:
                self.worker.portfolio[pid]["target"] = float(new_value)
                
            self.save_portfolio() 
        except ValueError:
            pass

    def update_table(self, pid, days, current_usd, current_total, simple_return, apr):
        self.active_table.blockSignals(True) 
        
        for row in range(self.active_table.rowCount()):
            item = self.active_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == pid:
                self.active_table.item(row, 1).setText(str(days))
                self.active_table.item(row, 7).setText(f"{current_usd:.2f}")
                self.active_table.item(row, 8).setText(f"{current_total:.2f}")
                
                ret_item = self.active_table.item(row, 9)
                ret_item.setText(f"{simple_return:.2f}%")
                ret_item.setForeground(Qt.GlobalColor.green if simple_return > 0 else Qt.GlobalColor.red)
                
                apr_item = self.active_table.item(row, 10)
                apr_item.setText(f"{apr:.2f}%")
                apr_item.setForeground(Qt.GlobalColor.green if apr > 0 else Qt.GlobalColor.red)
                break
                
        self.active_table.blockSignals(False)

    def delete_row(self, pid):
        if pid in self.worker.portfolio:
            del self.worker.portfolio[pid]
            
        for row in range(self.active_table.rowCount()):
            item = self.active_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == pid:
                self.active_table.removeRow(row)
                break
                
        self.save_portfolio()

    def save_portfolio(self):
        try:
            save_data = {
                "active": self.worker.portfolio,
                "history": self.history
            }
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Kayıt hatası: {e}")

    def load_portfolio(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # Eski tek boyutlu JSON versiyonunu yeni sekmeli yapıya uyarla
                    if "active" not in data:
                        data = {"active": data, "history": []}
                        
                    for pid, item in data.get("active", {}).items():
                        self.worker.portfolio[pid] = item
                        self.insert_row_to_active(
                            pid, item["date"], item["symbol"], 
                            item["lot"], item["entry_usd"], item["target"]
                        )
                    
                    self.history = data.get("history", [])
                    for hist in self.history:
                        self.insert_row_to_history(hist)
                        
            except Exception as e:
                print(f"Yükleme hatası: {e}")

    def closeEvent(self, event):
        self.save_portfolio()
        event.accept()

    def send_notification(self, symbol, current_usd, target_usd):
        notification.notify(
            title=f"Hedef Fiyat Alarmı: {symbol}",
            message=f"{symbol} hissesi {current_usd:.2f} USD hedefine ulaştı!",
            app_name="Borsa Terminali",
            timeout=10
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BorsaTerminali()
    window.show()
    sys.exit(app.exec())